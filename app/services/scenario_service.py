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
from typing import Dict, List, Optional, Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from app.models.scenario import ScenarioProgress, Scenario, Role, CompletionStatus


class ScenarioService:
    def __init__(self, db: AsyncSession):
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
            "당신은 한국어 말하기 연습을 도와주는 한국어 코칭 선생님입니다. "
            "반드시 한국어로만 대화하세요. 외국인 노동자를 대상으로 쉬운 단어를 사용하고, "
            "상대가 이해하기 어려워하면 예시를 들어 설명하세요. "
            "말이 끝날 때는 짧게 되물어보며 대화를 이어가세요. 필요하면 자연스럽게 표현을 교정하고, "
            "공손하고 친절한 톤을 유지하세요.\n\n"
            f"**역할 설정 (매우 중요!)**\n"
            f"- 학습자의 역할: '{user_role}'\n"
            f"- AI의 역할(당신의 역할): '{ai_role}'\n"
            f"- 대화 주제: {topic}\n\n"
        )
        if description:
            prompt += f"**상황 설명:** {description}\n\n"
        
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
        await self.db.commit()
        await self.db.refresh(scenario)

        # User Role  생성
        user_role_obj = Role(
            role_name=user_role,
        )
        self.db.add(user_role_obj)
        await self.db.commit()
        await self.db.refresh(user_role_obj)

        # AI Role  생성
        ai_role_obj = Role(
            role_name=ai_role,
        )
        self.db.add(ai_role_obj)
        await self.db.commit()
        await self.db.refresh(ai_role_obj)

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

            # 2) 초기 사용자 메시지 추가 (한국어 코칭 형식)
            # 한국어 코칭을 시작하도록 요청
            initial_message = (
                f"한국어 말하기 연습을 시작하겠습니다. "
                f"**역할을 명확히 기억하세요:** 사용자는 '{user_role}' 역할을 연습하고 있고, AI는 '{ai_role}' 역할입니다. "
                f"'{user_role}' 역할에서 말할 수 있는 자연스러운 한국어 문장을 제시하고, "
                f"그 문장에 대해 '{ai_role}' 역할로서 어떻게 대답할지 코칭해주세요. "
                f"**올바른 예시 형식:** \"{ai_role}이 \"[문장]\", 라고 할 수 있어요. 이럴땐 {user_role}은 어떻게 대답하실거에요?\" "
            )
            
            await client.post(
                f"{self.base_url}/threads/{thread_id}/messages",
                headers=headers,
                json={"role": "user", "content": initial_message},
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
        result = await self.db.execute(
            select(ScenarioProgress).where(ScenarioProgress.thread_id == thread_id)
        )
        db_progress = result.scalar_one_or_none()

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

        await self.db.commit()

        return {"session_id": session_id, "assistant": assistant_text, "assistant_id": aid}

    async def send_message(self, thread_id: str, user_text: str) -> Dict[str, str]:
        """기존 thread에 사용자 메시지 추가 후 run 실행 및 응답 반환"""
        self._ensure_api_key()

        # DB에서 세션 정보 조회 (thread_id로 찾기)
        result = await self.db.execute(
            select(ScenarioProgress).where(ScenarioProgress.thread_id == thread_id)
        )
        db_progress = result.scalar_one_or_none()

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
            await self.db.commit()

        return {"assistant": assistant_text}

    async def end_scenario(self, thread_id: str) -> Dict[str, str]:
        """시나리오 종료: completion_status를 COMPLETED로 변경하고 end_time 저장, 대화 기록 저장"""
        # DB에서 세션 정보 조회
        result = await self.db.execute(
            select(ScenarioProgress).where(ScenarioProgress.thread_id == thread_id)
        )
        db_progress = result.scalar_one_or_none()
        
        if not db_progress:
            raise ValueError(f"thread_id {thread_id}에 해당하는 시나리오 진행 상황을 찾을 수 없습니다.")
        
        # 시나리오 종료 전 대화 기록 저장
        try:
            await self.save_conversation_to_db(thread_id)
        except Exception as e:
            # 대화 기록 저장 실패해도 종료는 진행
            print(f"대화 기록 저장 실패 (시나리오 종료는 계속 진행): {str(e)}")
        
        # 시나리오 종료 처리
        db_progress.completion_status = CompletionStatus.COMPLETED
        db_progress.end_time = datetime.utcnow()
        
        await self.db.commit()
        
        return {
            "thread_id": thread_id,
            "completion_status": db_progress.completion_status.value,
            "end_time": db_progress.end_time.isoformat() if db_progress.end_time else None,
            "turn_count": db_progress.turn_count or 0,
        }

    async def get_completed_scenarios(self, user_id: int) -> List[ScenarioProgress]:
        """사용자의 완료된 시나리오 목록 조회"""
        result = await self.db.execute(
            select(ScenarioProgress)
            .where(
                ScenarioProgress.user_id == user_id,
                ScenarioProgress.completion_status == CompletionStatus.COMPLETED
            )
            .options(selectinload(ScenarioProgress.scenario))
            .order_by(ScenarioProgress.end_time.desc())
        )
        return list(result.scalars().all())
    
    async def get_user_turn_count(self, user_id: int) -> Dict[str, int]:
        """
        사용자의 전체 발화 횟수 조회
        
        Args:
            user_id: 사용자 ID
            
        Returns:
            Dict: 발화 횟수 통계
        """
        # 전체 발화 횟수 합산 (turn_count가 NULL이 아닌 경우만)
        total_turn_count_result = await self.db.execute(
            select(func.coalesce(func.sum(ScenarioProgress.turn_count), 0))
            .where(ScenarioProgress.user_id == user_id)
        )
        total_turn_count = total_turn_count_result.scalar() or 0
        
        # 시나리오 개수
        scenario_count_result = await self.db.execute(
            select(func.count(ScenarioProgress.progress_id))
            .where(ScenarioProgress.user_id == user_id)
        )
        scenario_count = scenario_count_result.scalar() or 0
        
        return {
            "user_id": user_id,
            "total_turn_count": int(total_turn_count),
            "scenario_count": int(scenario_count)
        }
    
    
    async def get_conversation(self, progress_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        """
        DB에서 저장된 대화 기록 조회 (progress_id로 조회)
        
        Args:
            progress_id: ScenarioProgress의 progress_id
            user_id: 사용자 ID (권한 확인용)
            
        Returns:
            Dict: 대화 기록 정보 (없으면 None)
        """
        result = await self.db.execute(
            select(ScenarioProgress)
            .where(
                ScenarioProgress.progress_id == progress_id,
                ScenarioProgress.user_id == user_id
            )
            .options(selectinload(ScenarioProgress.scenario))
        )
        db_progress = result.scalar_one_or_none()
        
        if not db_progress:
            return None
        
        # conversation 필드에서 대화 기록 가져오기
        conversation = db_progress.conversation
        
        return {
            "thread_id": db_progress.thread_id or "",
            "scenario_title": db_progress.scenario.title if db_progress.scenario else None,
            "messages": conversation if conversation else [],
            "total_messages": len(conversation) if conversation else 0
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

    #대화내역 json 저장
    async def save_conversation_to_db(self, thread_id: str) -> bool:
        """
        OpenAI Assistants API에서 메시지 리스트를 조회하여 conversation 필드에 JSON 형태로 저장
        
        Args:
            thread_id: OpenAI Thread ID
            
        Returns:
            bool: 저장 성공 여부
        """
        self._ensure_api_key()
        
        # DB에서 세션 정보 조회
        result = await self.db.execute(
            select(ScenarioProgress).where(ScenarioProgress.thread_id == thread_id)
        )
        db_progress = result.scalar_one_or_none()
        
        if not db_progress:
            raise ValueError(f"thread_id {thread_id}에 해당하는 시나리오 진행 상황을 찾을 수 없습니다.")
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "OpenAI-Beta": "assistants=v2",
        }
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                # OpenAI Assistants API에서 메시지 리스트 조회
                # order=asc로 하면 시간순으로 정렬됨
                response = await client.get(
                    f"{self.base_url}/threads/{thread_id}/messages?order=asc&limit=100",
                    headers=headers
                )
                response.raise_for_status()
                data = response.json()
                
                messages_data = data.get("data", [])
                
                # 메시지를 JSON 형태로 변환
                conversation_list: List[Dict[str, Any]] = []
                
                # 제외할 초기 사용자 메시지
                INITIAL_USER_MESSAGE = "안녕하세요. 저는 연습을 시작하려고 합니다. 주제에 맞게 간단한 질문으로 시작해 주세요."
                
                for msg in messages_data:
                    role = msg.get("role")  # "user" or "assistant"
                    created_at_timestamp = msg.get("created_at")  # Unix timestamp
                    content_list = msg.get("content", [])
                    
                    # content에서 text만 추출
                    text_parts: List[str] = []
                    for content in content_list:
                        if content.get("type") == "text":
                            text_value = content.get("text", {}).get("value", "")
                            if text_value:
                                text_parts.append(text_value)
                    
                    if text_parts:
                        full_content = "\n".join(text_parts).strip()
                        
                        # 초기 사용자 메시지는 제외
                        if role == "user" and full_content == INITIAL_USER_MESSAGE:
                            continue
                        
                        # Unix timestamp를 yyyy-mm-dd 형식으로 변환
                        created_at_str = None
                        if created_at_timestamp:
                            try:
                                # Unix timestamp를 datetime 객체로 변환
                                created_at_dt = datetime.fromtimestamp(created_at_timestamp)
                                # yyyy-mm-dd 형식으로 변환
                                created_at_str = created_at_dt.strftime("%Y-%m-%d")
                            except (ValueError, TypeError, OSError):
                                # 변환 실패 시 현재 시간 사용
                                created_at_str = datetime.utcnow().strftime("%Y-%m-%d")
                        
                        conversation_list.append({
                            "role": role,
                            "content": full_content,
                            "created_at": created_at_str
                        })
                
                # conversation 필드에 저장
                db_progress.conversation = conversation_list
                await self.db.commit()
                
                return True
                
        except httpx.HTTPStatusError as e:
            raise ValueError(f"OpenAI API 호출 실패: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            raise ValueError(f"대화 기록 저장 중 오류: {str(e)}")


