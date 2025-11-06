"""
한국어 AI 말하기 연습실 서비스 (OpenAI Assistants API - Threads 기반)

요구사항:
- 입력: 대화주제, 나의역할, AI의역할 (필수)
- 동작: 한국어로만 대화, 외국인 노동자 맞춤형 쉬운 문장과 느린 진행, 한 번에 한 질문
- 세션: thread_id를 session_id로 사용하여 서버 측 기억 유지 (OpenAI 저장)

환경변수:
- OPENAI_API_KEY (필수)
- OPENAI_MODEL (선택, 기본 gpt-4o-mini)
- OPENAI_BASE_URL (선택, 기본 https://api.openai.com/v1)
- OPENAI_ASSISTANT_ID (선택, 없으면 런타임에 생성)
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional

import httpx
from sqlalchemy.orm import Session
from app.models.scenario import ScenarioProgress, Scenario, Role, CompletionStatus


class ScenarioService:
    def __init__(self, db: Session):
        self.db = db
        self.api_key = os.environ.get("OPENAI_API_KEY")
        self.model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        self.base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.assistant_id = None  # _ensure_assistant_ready에서 생성됨

    def _ensure_api_key(self) -> None:
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다.")

    def _build_system_prompt(self, topic: str, user_role: str, ai_role: str, description: Optional[str] = None) -> str:
        prompt = (
            "당신은 한국어 말하기 연습을 도와주는 코치입니다. "
            "반드시 한국어로만 대화하세요. 외국인 노동자를 대상으로 쉬운 단어를 사용하고, "
            "상대가 이해하기 어려워하면 예시를 들어 설명하세요. "
            "말이 끝날 때는 짧게 되물어보며 대화를 이어가세요. 필요하면 자연스럽게 표현을 교정하고, "
            "공손하고 친절한 톤을 유지하세요.\n\n"
            f"대화 주제: {topic}\n"
            f"사용자 역할: {user_role}\n"
            f"AI 역할: {ai_role}"
        )
        if description:
            prompt += f"\n상황 설명: {description}"
        return prompt
    async def start_scenario(self, user_id: int, topic: str, user_role: str, ai_role: str, description: Optional[str] = None) -> Dict[str, str]:
        """Assistants API로 스레드 생성, 초기 질문 수행, 첫 응답 반환"""
        self._ensure_api_key()
        await self._ensure_assistant_ready(topic, user_role, ai_role, description)   # 항상 새로운 assistant 생성
        aid = self.assistant_id #assistant 아이디 반환
        if not aid:
            raise ValueError("Assistant 생성에 실패했습니다.")
        
        # Scenario  생성
        scenario = Scenario(
            title=topic,
            description=f"대화 주제: {topic}",
        )
        self.db.add(scenario)
        self.db.commit()
        self.db.refresh(scenario)
        
        # User Role  생성
        user_role_obj = Role(
            role_name=user_role,
            description=f"사용자 역할: {user_role}",
        )
        self.db.add(user_role_obj)
        self.db.commit()
        self.db.refresh(user_role_obj)
        
        # AI Role  생성
        ai_role_obj = Role(
            role_name=ai_role,
            description=f"AI 역할: {ai_role}",
        )
        self.db.add(ai_role_obj)
        self.db.commit()
        self.db.refresh(ai_role_obj)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "OpenAI-Beta": "assistants=v2",
        }

        # 1) thread 생성
        async with httpx.AsyncClient(timeout=60.0) as client: #60초 동안 응답 없으면 에러 발생
            thr = await client.post(f"{self.base_url}/threads", headers=headers, json={}) #thread 생성
            thr.raise_for_status()  #정상 반환이 아니면 예외 발생(raise_for_status)
            thread_id = thr.json()["id"] #스레드 아이디 반환

            # 2) 초기 사용자 메시지 추가
            await client.post(
                f"{self.base_url}/threads/{thread_id}/messages",
                headers=headers,
                json={"role": "user", "content": "안녕하세요. 저는 연습을 시작하려고 합니다. 주제에 맞게 간단한 질문으로 시작해 주세요."},
            )

            # 3) run 생성(assistant 호출)
            run = await client.post(
                f"{self.base_url}/threads/{thread_id}/runs",
                headers=headers,
                json={"assistant_id": aid},
            )
            run.raise_for_status()
            run_id = run.json()["id"]
            # 4) run 완료 대기
            await self._wait_run_complete(client, headers, thread_id, run_id)
            # 5) 최신 assistant 메시지 조회
            assistant_text = await self._get_latest_assistant_message(client, headers, thread_id)

        session_id = thread_id
        
        # DB에 ScenarioProgress 저장/업데이트
        # 기존 progress가 있으면 업데이트, 없으면 새로 생성
        db_progress = self.db.query(ScenarioProgress).filter(
            ScenarioProgress.thread_id == thread_id
        ).first()
        
        if db_progress:
            # 기존 레코드 업데이트
            db_progress.user_id = user_id
            db_progress.scenario_id = scenario.scenario_id
            db_progress.user_role_id = user_role_obj.role_id
            db_progress.ai_role_id = ai_role_obj.role_id
            db_progress.assistant_id = aid
            db_progress.thread_id = thread_id
            db_progress.completion_status = CompletionStatus.IN_PROGRESS
            db_progress.turn_count = 0
            db_progress.start_time = datetime.utcnow()
            db_progress.end_time = None
            if description:
                db_progress.description = description
        else:
            # 새 레코드 생성 (인증된 사용자 ID 사용)
            db_progress = ScenarioProgress(
                user_id=user_id,
                scenario_id=scenario.scenario_id,
                user_role_id=user_role_obj.role_id,
                ai_role_id=ai_role_obj.role_id,
                thread_id=thread_id,
                assistant_id=aid,
                description=description,
                completion_status=CompletionStatus.IN_PROGRESS,
                turn_count=0,
            )
            self.db.add(db_progress)
        
        self.db.commit()
        
        return {"session_id": session_id, "assistant": assistant_text, "assistant_id": aid}

    async def send_message(self, thread_id: str, user_text: str) -> Dict[str, str]:
        """기존 thread에 사용자 메시지 추가 후 run 실행 및 응답 반환"""
        self._ensure_api_key()

        # DB에서 세션 정보 조회 (thread_id로 찾기)
        db_progress = self.db.query(ScenarioProgress).filter(
            ScenarioProgress.thread_id == thread_id
        ).first()
        
        if not db_progress:
            # DB에 없으면 thread_id를 직접 사용하되 assistant_id가 필요
            aid = self.assistant_id
            if not aid:
                raise ValueError("유효하지 않은 thread_id입니다. 세션을 먼저 시작해주세요.")
        else:
            # DB에서 찾은 thread_id와 assistant_id 사용
            thread_id = db_progress.thread_id or thread_id
            aid = db_progress.assistant_id
            if not aid:
                raise ValueError("assistant_id가 설정되지 않은 세션입니다.")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "OpenAI-Beta": "assistants=v2",
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            # 1) 사용자 메시지 추가
            await client.post(
                f"{self.base_url}/threads/{thread_id}/messages",
                headers=headers,
                json={"role": "user", "content": user_text},
            )

            # 2) run 생성
            run = await client.post(
                f"{self.base_url}/threads/{thread_id}/runs",
                headers=headers,
                json={"assistant_id": aid},
            )
            run.raise_for_status()
            run_id = run.json()["id"]

            # 3) 완료 대기 후 응답 획득
            await self._wait_run_complete(client, headers, thread_id, run_id)
            assistant_text = await self._get_latest_assistant_message(client, headers, thread_id)

        # DB에서 발화 횟수 증가 (사용자 메시지 전송 시)
        if db_progress:
            if db_progress.turn_count is None:
                db_progress.turn_count = 0
            db_progress.turn_count += 1
            self.db.commit()

        return {"assistant": assistant_text}

    async def end_scenario(self, thread_id: str) -> Dict[str, str]:
        """시나리오 종료: completion_status를 COMPLETED로 변경하고 end_time 저장"""
        # DB에서 세션 정보 조회
        db_progress = self.db.query(ScenarioProgress).filter(
            ScenarioProgress.thread_id == thread_id
        ).first()
        
        if not db_progress:
            raise ValueError(f"thread_id {thread_id}에 해당하는 시나리오 진행 상황을 찾을 수 없습니다.")
        
        # 시나리오 종료 처리
        db_progress.completion_status = CompletionStatus.COMPLETED
        db_progress.end_time = datetime.utcnow()
        
        self.db.commit()
        
        return {
            "thread_id": thread_id,
            "completion_status": db_progress.completion_status.value,
            "end_time": db_progress.end_time.isoformat() if db_progress.end_time else None,
            "turn_count": db_progress.turn_count or 0,
        }

    async def _ensure_assistant_ready(self, topic: str, user_role: str, ai_role: str, description: Optional[str] = None) -> None:
        """항상 새로운 assistant 생성"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "OpenAI-Beta": "assistants=v2",
        }
        instructions = self._build_system_prompt(topic, user_role, ai_role, description) #프롬프트에 처음 지시할 내용
        payload = {"model": self.model, "instructions": instructions} #프롬프트에 처음 지시할 내용을 전달

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{self.base_url}/assistants", headers=headers, json=payload) #assistant 생성
            resp.raise_for_status() #정상 반환이 아니면 예외 발생(raise_for_status)
            self.assistant_id = resp.json()["id"] #assistant 아이디 반환

#OpenAI Assistants의 run 상태가 완료될 때까지 폴링(주기적 조회)하는 비동기 함수입니다.
    async def _wait_run_complete(
        self,
        client: httpx.AsyncClient,
        headers: Dict[str, str],
        thread_id: str,
        run_id: str,
        *,
        max_wait_s: int = 60,
        poll_interval_s: float = 0.7,
    ) -> None:
        import asyncio

        waited = 0.0
        while True:
            r = await client.get(
                f"{self.base_url}/threads/{thread_id}/runs/{run_id}", headers=headers
            )
            r.raise_for_status() #정상 반환이 아니면 예외 발생(raise_for_status)
            status = r.json().get("status") #run 상태 반환
            if status in ("completed", "requires_action"): #완료 또는 필요한 작업이 있으면 종료
                return
            if status in ("failed", "cancelled", "expired"): #실패, 취소, 만료 상태 예외 발생
                raise RuntimeError(f"run 상태 오류: {status}")
            await asyncio.sleep(poll_interval_s) #0.7초 대기
            waited += poll_interval_s
            if waited >= max_wait_s: #60초 초과 시 예외 발생
                raise TimeoutError("응답 대기 시간 초과") #TimeoutError 예외 발생

#OpenAI Assistants의 최신 메시지를 조회하는 비동기 함수입니다.
    async def _get_latest_assistant_message(
        self,
        client: httpx.AsyncClient,
        headers: Dict[str, str],
        thread_id: str,
    ) -> str:
        msgs = await client.get(
            f"{self.base_url}/threads/{thread_id}/messages?limit=10",
            headers=headers,
        )
        msgs.raise_for_status()
        data = msgs.json().get("data", [])
        for m in data:
            if m.get("role") == "assistant":
                contents = m.get("content", [])
                # text 블록만 취합
                parts: List[str] = []
                for c in contents:
                    if c.get("type") == "text":
                        txt = c.get("text", {}).get("value", "")
                        if txt:
                            parts.append(txt)
                if parts:
                    return "\n".join(parts).strip()
        return "죄송하지만 지금은 답변을 생성하지 못했습니다. 다시 시도해 주세요."


