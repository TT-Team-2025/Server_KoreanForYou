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

import json
import os
import re
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from app.models.scenario import ScenarioProgress, Scenario, Role, CompletionStatus, ScenarioFeedback


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
            db_progress.start_time = datetime.now()
            db_progress.end_time = None
            db_progress.total_time = None
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
                start_time=datetime.now(),
                total_time=None,
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

    MIN_TURN_COUNT_FOR_COMPLETION = 5 #최소 발화횟수

    async def end_scenario(self, thread_id: str) -> Dict[str, str]:
        """시나리오 종료: completion_status를 COMPLETED로 변경하고 end_time 저장, 대화 기록 저장"""
        # DB에서 세션 정보 조회
        result = await self.db.execute(
            select(ScenarioProgress).where(ScenarioProgress.thread_id == thread_id)
        )
        db_progress = result.scalar_one_or_none()
        
        if not db_progress:
            raise ValueError(f"thread_id {thread_id}에 해당하는 시나리오 진행 상황을 찾을 수 없습니다.")
        
        turn_count = db_progress.turn_count or 0

        if turn_count < self.MIN_TURN_COUNT_FOR_COMPLETION:
            return {
                "thread_id": thread_id,
                "completion_status": db_progress.completion_status.value,
                "end_time": db_progress.end_time.isoformat() if db_progress.end_time else None,
                "turn_count": turn_count,
                "total_time": db_progress.total_time,
                "message": f"발화 횟수가 {self.MIN_TURN_COUNT_FOR_COMPLETION}회 미만이므로 완료 처리되지 않았습니다.",
            }
        
        # 시나리오 종료 전 대화 기록 저장
        try:
            await self.save_conversation_to_db(thread_id)
            await self.db.refresh(db_progress)
        except Exception as e:
            # 대화 기록 저장 실패해도 종료는 진행
            print(f"대화 기록 저장 실패 (시나리오 종료는 계속 진행): {str(e)}")
        
        # 시나리오 종료 처리
        db_progress.completion_status = CompletionStatus.COMPLETED
        end_time = datetime.now()
        db_progress.end_time = end_time
        if db_progress.start_time:
            total_time_delta = end_time - db_progress.start_time
            db_progress.total_time = int(total_time_delta.total_seconds())
        else:
            db_progress.total_time = None
        
        await self.db.commit()
        await self.db.refresh(db_progress)

        feedback_payload = await self._finalize_session_feedback(db_progress)
        
        return {
            "thread_id": thread_id,
            "completion_status": db_progress.completion_status.value,
            "end_time": db_progress.end_time.isoformat() if db_progress.end_time else None,
            "turn_count": db_progress.turn_count or 0,
            "total_time": db_progress.total_time,
            "feedback": feedback_payload,
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

    async def get_session_summary(
        self,
        progress_id: int,
        user_id: int,
    ) -> Dict[str, Any]:
        """
        단일 시나리오 세션의 학습 요약(점수, 시간, 코멘트 등)을 반환
        """
        result = await self.db.execute(
            select(ScenarioProgress)
            .where(
                ScenarioProgress.progress_id == progress_id,
                ScenarioProgress.user_id == user_id,
            )
            .options(
                selectinload(ScenarioProgress.scenario),
                selectinload(ScenarioProgress.scenario_feedback),
            )
        )
        progress = result.scalar_one_or_none()
        if not progress:
            raise ValueError("해당 시나리오 세션을 찾을 수 없습니다.")

        feedback = progress.scenario_feedback[0] if progress.scenario_feedback else None

        pronunciation_score = feedback.pronunciation_score if feedback else None
        fluency_score = feedback.fluency_score if feedback else None
        grammar_score = feedback.accuracy_score if feedback else None
        total_score = feedback.total_score if feedback else None

        ai_comment = feedback.comment if feedback else None
        detail_comment = feedback.detail_comment if feedback else None
        created_at = feedback.created_at if feedback else None

        return {
            "progress_id": progress.progress_id,
            "thread_id": progress.thread_id,
            "scenario_title": progress.scenario.title if progress.scenario else None,
            "completion_status": progress.completion_status.value if progress.completion_status else None,
            "turn_count": progress.turn_count,
            "total_time": progress.total_time,
            "total_score": total_score,
            "pronunciation_score": pronunciation_score,
            "fluency_score": fluency_score,
            "grammar_score": grammar_score,
            "ai_comment": ai_comment,
            "detail_comment": detail_comment,
            "created_at": created_at,
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



    async def evaluate_speech_metrics(
        self,
        thread_id: str,
        stt_result: Dict[str, Any],
        *,
        transcript: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        RTZR STT 결과(타임스탬프 기반)를 활용해 발음, 유창성, 문법 점수를 계산
        """
        utterances = []
        if stt_result:
            results = stt_result.get("results") or {}
            if isinstance(results, dict):
                utterances = results.get("utterances") or []

        if not transcript:
            transcript = self._build_transcript_from_utterances(utterances)

        words = self._flatten_word_segments(utterances)
        pronunciation_score, pronunciation_detail = self._calculate_pronunciation_metrics(words, utterances)
        fluency_score, fluency_detail = self._calculate_fluency_metrics(words)
        grammar_detail = await self._evaluate_grammar_metrics(transcript, thread_id)
        grammar_score = grammar_detail.get("grammar_score")

        available_scores = [
            score for score in [pronunciation_score, fluency_score, grammar_score] if score is not None
        ]
        overall_score = (
            self._round_score(sum(available_scores) / len(available_scores))
            if available_scores
            else None
        )

        return {
            "overall_score": overall_score,
            "pronunciation_score": pronunciation_score,
            "fluency_score": fluency_score,
            "grammar_score": grammar_score,
            "details": {
                "pronunciation": pronunciation_detail,
                "fluency": fluency_detail,
                "grammar": grammar_detail,
                "transcript": transcript,
            },
        }

#발화마다 점수 계산해서 저장
    async def append_speech_metric(
        self,
        thread_id: str,
        user_text: str,
        evaluation: Dict[str, Any],
    ) -> None:
        """
        세션 진행 중 산출된 발화 평가 지표를 ScenarioProgress.speech_metrics에 누적 저장
        """
        result = await self.db.execute(
            select(ScenarioProgress).where(ScenarioProgress.thread_id == thread_id)
        )
        progress = result.scalar_one_or_none()
        if not progress:
            return

        metrics = list(progress.speech_metrics or [])

        entry = {
            "recorded_at": datetime.utcnow().isoformat(),
            "user_text": user_text,
            "scores": {
                "pronunciation": evaluation.get("pronunciation_score"),
                "fluency": evaluation.get("fluency_score"),
                "grammar": evaluation.get("grammar_score"),
                "overall": evaluation.get("overall_score"),
            },
            "details": evaluation.get("details"),
        }
        metrics.append(entry)
        progress.speech_metrics = metrics
        await self.db.commit()

    def _aggregate_speech_metrics(self, metrics: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not metrics:
            return {
                "pronunciation_score": None,
                "fluency_score": None,
                "grammar_score": None,
                "overall_score": None,
                "evaluated_turns": 0,
                "word_count": 0,
                "speaking_duration": 0.0,
                "total_audio_duration": 0.0,
                "per_turn": metrics,
                "grammar_detail": None,
            }

        def collect_score(name: str) -> List[float]:
            values: List[float] = []
            for item in metrics:
                score = (item.get("scores") or {}).get(name)
                if score is not None:
                    values.append(float(score))
            return values

        pronunciation_values = collect_score("pronunciation")
        fluency_values = collect_score("fluency")
        grammar_values = collect_score("grammar")

        def average(values: List[float]) -> Optional[float]:
            if not values:
                return None
            return round(sum(values) / len(values), 2)

        total_words = 0
        speaking_duration_total = 0.0
        total_duration_total = 0.0
        for item in metrics:
            detail = item.get("details") or {}
            pronunciation_detail = detail.get("pronunciation") or {}
            fluency_detail = detail.get("fluency") or {}
            total_words += pronunciation_detail.get("word_count") or 0
            speaking_duration_total += float(fluency_detail.get("speaking_duration") or 0.0)
            total_duration_total += float(fluency_detail.get("total_duration") or 0.0)

        pronunciation_avg = self._round_score(average(pronunciation_values)) if pronunciation_values else None
        fluency_avg = self._round_score(average(fluency_values)) if fluency_values else None
        grammar_avg = self._round_score(average(grammar_values)) if grammar_values else None
        overall = self._calculate_overall_score(pronunciation_avg, fluency_avg, grammar_avg)

        return {
            "pronunciation_score": pronunciation_avg,
            "fluency_score": fluency_avg,
            "grammar_score": grammar_avg,
            "overall_score": overall,
            "evaluated_turns": len(metrics),
            "word_count": total_words,
            "speaking_duration": round(speaking_duration_total, 2),
            "total_audio_duration": round(total_duration_total, 2),
            "per_turn": metrics,
            "grammar_detail": None,
        }

#총점 계산
    @staticmethod
    def _calculate_overall_score(
        pronunciation: Optional[float],
        fluency: Optional[float],
        grammar: Optional[float],
    ) -> Optional[int]:
        scores = [s for s in (pronunciation, fluency, grammar) if s is not None]
        if not scores:
            return None
        return ScenarioService._round_score(sum(scores) / len(scores))

    def _prepare_conversation_excerpt(
        self,
        conversation: List[Dict[str, Any]],
        limit: int = 12,
    ) -> str:
        if not conversation:
            return ""
        excerpt = conversation[-limit:]
        lines: List[str] = []
        for idx, msg in enumerate(excerpt, start=1):
            role = msg.get("role", "unknown")
            content = (msg.get("content") or "").strip()
            if not content:
                continue
            lines.append(f"{idx}. {role}: {content}")
        return "\n".join(lines)

    @staticmethod
    def _build_user_transcript(conversation: List[Dict[str, Any]]) -> str:
        if not conversation:
            return ""
        segments: List[str] = []
        for msg in conversation:
            if msg.get("role") == "user":
                content = (msg.get("content") or "").strip()
                if content:
                    segments.append(content)
        return "\n".join(segments)

    async def _generate_session_feedback_with_llm(
        self,
        metrics_summary: Dict[str, Any],
        conversation_excerpt: str,
    ) -> Dict[str, Any]:
        self._ensure_api_key()

        system_prompt = (
            "너는 한국어 말하기 연습을 평가하고 구체적인 피드백을 주는 전문 코치이다. "
            "발화 내용을 분석해 문장별 리뷰, 개선 사항, 격려 멘트를 제공하라. "
            "응답은 반드시 JSON 형식이어야 한다."
        )

        metrics_json = json.dumps(metrics_summary, ensure_ascii=False, indent=2)
        excerpt = conversation_excerpt or "대화 기록이 제공되지 않았습니다."

        user_prompt = (
            "다음은 학습자의 한국어 말하기 세션에 대한 평가 지표와 최근 대화 내용이다.\n\n"
            f"[평가 지표 요약]\n{metrics_json}\n\n"
            "[대화 발췌]\n"
            f"{excerpt}\n\n"
            "요구사항:\n"
            "1. JSON 객체 형식으로만 응답한다. (추가 설명 금지)\n"
            "2. 필수 필드는 아래와 같다.\n"
            "   - ai_comment: 전체에 대한 격려 및 요약 코멘트 (문자열)\n"
            "   - improvements: 향후 개선을 위한 구체적인 조언 목록 (문자열 배열)\n"
            "   - key_sentence_reviews: 최대 3개의 핵심 문장 리뷰 (각 항목은 객체로 sentence, issue, suggestion 필드를 포함)\n"
            "   - highlights: 잘한 점을 1~3가지로 정리한 문자열 배열\n"
            "3. key_sentence_reviews에서 sentence는 학습자의 발화 문장을 그대로 사용하라.\n"
            "4. improvements와 highlights는 짧고 명확한 한국어 문장으로 작성하라.\n"
            "5. JSON 외의 텍스트는 절대 포함하지 않는다."
        )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.4,
            "max_tokens": 600,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                response = await client.post(
                    f"{self.base_url.rstrip('/')}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
        except Exception as exc:
            print(f"[SessionFeedback] OpenAI 호출 실패: {exc}")
            return {}

        parsed = self._parse_llm_json(content)
        return parsed or {}

    async def _finalize_session_feedback(self, progress: ScenarioProgress) -> Optional[Dict[str, Any]]:
        metrics = progress.speech_metrics or []
        metrics_summary = self._aggregate_speech_metrics(metrics)

        conversation = progress.conversation or []
        conversation_excerpt = self._prepare_conversation_excerpt(conversation)
        user_transcript = self._build_user_transcript(conversation)

        if metrics_summary.get("grammar_score") is None and user_transcript:
            grammar_detail = await self._evaluate_grammar_metrics(user_transcript, progress.thread_id or "")
            metrics_summary["grammar_score"] = grammar_detail.get("grammar_score")
            metrics_summary["grammar_detail"] = grammar_detail
            metrics_summary["overall_score"] = self._calculate_overall_score(
                metrics_summary.get("pronunciation_score"),
                metrics_summary.get("fluency_score"),
                metrics_summary.get("grammar_score"),
            )
        elif metrics_summary.get("grammar_detail") is None:
            metrics_summary["grammar_detail"] = {}

        llm_feedback = await self._generate_session_feedback_with_llm(
            metrics_summary,
            conversation_excerpt,
        )

        feedback_record = await self._create_or_update_feedback_record(
            progress=progress,
            metrics_summary=metrics_summary,
            llm_feedback=llm_feedback,
        )

        if not feedback_record:
            return None

        detail_comment = feedback_record.detail_comment or {}
        return {
            "feedback_id": feedback_record.feedback_id,
            "user_id": feedback_record.user_id,
            "log_id": feedback_record.log_id,
            "pronunciation_score": feedback_record.pronunciation_score,
            "fluency_score": feedback_record.fluency_score,
            "grammar_score": feedback_record.accuracy_score,
            "overall_score": feedback_record.total_score,
            "comment": feedback_record.comment,
            "detail_comment": detail_comment,
            "created_at": feedback_record.created_at.isoformat() if feedback_record.created_at else None,
        }

    async def _create_or_update_feedback_record(
        self,
        progress: ScenarioProgress,
        metrics_summary: Dict[str, Any],
        llm_feedback: Dict[str, Any],
    ) -> Optional[ScenarioFeedback]:
        pronunciation_score = metrics_summary.get("pronunciation_score")
        fluency_score = metrics_summary.get("fluency_score")
        grammar_score = metrics_summary.get("grammar_score")
        overall_score = metrics_summary.get("overall_score")

        rounded_pronunciation = self._round_score(pronunciation_score)
        rounded_fluency = self._round_score(fluency_score)
        rounded_grammar = self._round_score(grammar_score) if grammar_score is not None else 0

        if overall_score is None:
            available_scores = [
                score for score in (rounded_pronunciation, rounded_fluency, rounded_grammar) if score is not None
            ]
            overall_score = (
                self._round_score(sum(available_scores) / len(available_scores)) if available_scores else None
            )

        detail_payload: Dict[str, Any] = {
            "improvements": llm_feedback.get("improvements") or [],
            "key_sentence_reviews": llm_feedback.get("key_sentence_reviews") or [],
            "highlights": llm_feedback.get("highlights") or [],
            "ai_comment": llm_feedback.get("ai_comment"),
            "metrics_summary": metrics_summary,
            "session_stats": {
                "evaluated_turns": metrics_summary.get("evaluated_turns"),
                "word_count": metrics_summary.get("word_count"),
                "speaking_duration_seconds": metrics_summary.get("speaking_duration"),
                "total_audio_duration_seconds": metrics_summary.get("total_audio_duration"),
                "turn_count": progress.turn_count,
                "total_time_seconds": progress.total_time,
            },
        }

        existing_result = await self.db.execute(
            select(ScenarioFeedback).where(ScenarioFeedback.log_id == progress.progress_id)
        )
        feedback = existing_result.scalar_one_or_none()

        if not feedback:
            feedback = ScenarioFeedback(
                user_id=progress.user_id,
                log_id=progress.progress_id,
            )
            self.db.add(feedback)

        feedback.pronunciation_score = rounded_pronunciation
        feedback.fluency_score = rounded_fluency
        feedback.accuracy_score = rounded_grammar
        feedback.total_score = self._round_score(overall_score)
        feedback.comment = llm_feedback.get("ai_comment")
        feedback.detail_comment = detail_payload

        await self.db.commit()
        await self.db.refresh(feedback)
        return feedback

    @staticmethod
    def _round_score(value: Optional[float]) -> Optional[int]:
        if value is None:
            return None
        return int(round(float(value)))

    def _build_transcript_from_utterances(self, utterances: List[Dict[str, Any]]) -> str:
        segments: List[str] = []
        for utter in utterances:
            text = (
                utter.get("msg")
                or utter.get("text")
                or utter.get("transcript")
                or ""
            )
            if text:
                segments.append(str(text).strip())
        return " ".join(segments).strip()

    def _flatten_word_segments(self, utterances: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        words: List[Dict[str, Any]] = []
        for idx, utter in enumerate(utterances):
            utter_words = utter.get("words") or []
            for word in utter_words:
                text = (word.get("msg") or word.get("text") or word.get("word") or "").strip()
                start = self._normalize_timestamp(
                    word.get("start_at")
                    or word.get("start")
                    or word.get("begin_at")
                )
                end = self._normalize_timestamp(
                    word.get("end_at")
                    or word.get("end")
                    or word.get("finish_at")
                )
                duration = self._normalize_duration(word.get("duration") or word.get("duration_ms"))
                confidence = self._safe_float(word.get("confidence") or word.get("score"))
                if not text:
                    continue
                if start is None and utter.get("start_at") is not None:
                    start = self._normalize_timestamp(utter.get("start_at"))
                if end is None and utter.get("end_at") is not None:
                    end = self._normalize_timestamp(utter.get("end_at"))
                if duration is None and utter.get("duration") is not None:
                    duration = self._normalize_duration(utter.get("duration"))
                if end is None and start is not None and duration is not None:
                    end = start + duration
                if start is None and end is not None and duration is not None:
                    start = end - duration
                if duration is None and start is not None and end is not None:
                    duration = max(0.0, end - start)
                words.append(
                    {
                        "text": text,
                        "start": start,
                        "end": end,
                        "duration": duration,
                        "confidence": confidence,
                        "utterance_index": idx,
                    }
                )
        words.sort(key=lambda x: (x["start"] if x["start"] is not None else float("inf")))
        return words

    def _calculate_pronunciation_metrics(
        self,
        words: List[Dict[str, Any]],
        utterances: List[Dict[str, Any]],
    ) -> Tuple[Optional[float], Dict[str, Any]]:
        confidences: List[float] = [
            w["confidence"] for w in words if w.get("confidence") is not None
        ]

        if not confidences:
            utter_conf = [
                self._safe_float(u.get("confidence")) for u in utterances
                if self._safe_float(u.get("confidence")) is not None
            ]
            confidences = utter_conf

        detail: Dict[str, Any] = {
            "word_count": len(words),
            "metrics_source": "confidence" if confidences else "duration",
        }

        if confidences:
            avg_conf = sum(confidences) / len(confidences)
            variance = sum((c - avg_conf) ** 2 for c in confidences) / len(confidences)
            std_dev = variance ** 0.5
            low_threshold = 0.75
            low_count = sum(1 for c in confidences if c < low_threshold)
            low_ratio = low_count / len(confidences)

            low_conf_words = [
                w["text"]
                for w in words
                if w.get("confidence") is not None and w["confidence"] < low_threshold
            ][:10]

            score = (avg_conf * 100) - (low_ratio * 25) - (std_dev * 15)
            score = self._clamp_score(score)

            detail.update(
                {
                    "confidence_stddev": round(std_dev, 4),
                    "low_confidence_ratio": round(low_ratio, 4),
                    "low_confidence_words": low_conf_words,
                }
            )
            return score, detail

        durations = [w["duration"] for w in words if w.get("duration") is not None]
        detail.update(
            {
                "duration_count": len(durations),
                "average_duration": None,
                "short_duration_ratio": None,
                "long_duration_ratio": None,
            }
        )

        if not durations:
            return 80.0, detail

        avg_duration = sum(durations) / len(durations)
        # 발음 길이 기준: 0.18초 이하는 과도하게 짧은 발음으로 간주
        short_threshold = 0.18
        long_threshold = 1.8

        short_count = sum(1 for d in durations if d < short_threshold)
        long_count = sum(1 for d in durations if d > long_threshold)
        short_ratio = short_count / len(durations)
        long_ratio = long_count / len(durations)

        duration_outliers = [
            w["text"]
            for w in words
            if w.get("duration") is not None and (w["duration"] < short_threshold or w["duration"] > long_threshold)
        ][:10]

        base_score = 95.0
        short_penalty = min(50.0, short_ratio * 110.0)
        long_penalty = min(30.0, long_ratio * 70.0)
        stability_penalty = min(15.0, self._compute_duration_variation_penalty(durations))

        score = self._clamp_score(base_score - short_penalty - long_penalty - stability_penalty)

        detail.update(
            {
                "average_duration": round(avg_duration, 4),
                "short_duration_ratio": round(short_ratio, 4),
                "long_duration_ratio": round(long_ratio, 4),
                "duration_outlier_words": duration_outliers,
            }
        )
        return score, detail

    def _calculate_fluency_metrics(
        self,
        words: List[Dict[str, Any]],
    ) -> Tuple[Optional[float], Dict[str, Any]]:
        detail: Dict[str, Any] = {
            "word_count": len(words),
            "words_per_minute": None,
            "pause_count": 0,
            "average_pause": 0.0,
            "filler_count": 0,
            "speaking_duration": 0.0,
            "total_duration": 0.0,
        }

        if not words:
            return None, detail

        valid_words = [w for w in words if w.get("start") is not None and w.get("end") is not None]
        if not valid_words:
            return None, detail

        speaking_start = valid_words[0]["start"]
        speaking_end = valid_words[-1]["end"]
        total_duration = max(0.0, speaking_end - speaking_start) if speaking_start is not None else 0.0
        speaking_duration = sum((w["duration"] or 0.0) for w in valid_words)
        words_per_min = 0.0
        if total_duration > 0:
            words_per_min = len(valid_words) / total_duration * 60.0

        pauses: List[float] = []
        for prev, curr in zip(valid_words, valid_words[1:]):
            prev_end = prev.get("end")
            curr_start = curr.get("start")
            if prev_end is None or curr_start is None:
                continue
            gap = curr_start - prev_end
            if gap >= 1.0:
                pauses.append(gap)

        average_pause = sum(pauses) / len(pauses) if pauses else 0.0
        filler_words = {"음", "어", "저기", "그", "음...", "어...", "에", "그러니까", "뭐랄까"}
        filler_count = sum(1 for w in valid_words if w["text"] in filler_words)

        detail.update(
            {
                "words_per_minute": round(words_per_min, 2),
                "pause_count": len(pauses),
                "average_pause": round(average_pause, 2),
                "filler_count": filler_count,
                "speaking_duration": round(speaking_duration, 2),
                "total_duration": round(total_duration, 2),
            }
        )

        if total_duration <= 0:
            return None, detail

        target_wpm = 130.0
        wpm_deviation = abs(words_per_min - target_wpm) / target_wpm
        wpm_penalty = min(35.0, wpm_deviation * 55.0)

        pause_penalty = min(30.0, len(pauses) * 4.0 + max(0.0, (average_pause - 1.5) * 6.0))
        filler_penalty = min(20.0, (filler_count / max(1, len(valid_words))) * 45.0)

        base_score = 100.0 - (wpm_penalty + pause_penalty + filler_penalty)
        score = self._clamp_score(base_score)

        return score, detail

    async def _evaluate_grammar_metrics(
        self,
        transcript: str,
        thread_id: str,
    ) -> Dict[str, Any]:
        if not transcript:
            return {
                "grammar_score": None,
                "mistakes": [],
                "suggestions": [],
            }

        self._ensure_api_key()

        system_prompt = (
            "너는 한국어 발화의 문법과 표현을 분석하는 교정 전문가이다. "
            "사용자의 발화에서 문법 오류와 어색한 표현을 찾아내고, 점수(0-100)를 계산한다. "
            "결과는 반드시 JSON 형식으로 반환한다."
        )

        user_prompt = (
            "다음은 학습자의 발화 전체 전사본이다.\n"
            "```\n"
            f"{transcript.strip()}\n"
            "```\n\n"
            "분석 지침:\n"
            "1. 문장 구조, 조사, 시제, 어순, 어휘 사용 오류를 찾아라.\n"
            "2. 오류가 없으면 높은 점수(90 이상)를 부여하되, 이유를 짧게 설명하라.\n"
            "3. 발견한 오류마다 간단한 설명과 올바른 표현 예시를 제시하라.\n"
            "4. JSON 객체로 응답하고, 필드는 grammar_score(정수), mistakes(문자열 배열), suggestions(문자열 배열)이다.\n"
            "5. JSON만 반환하고 추가 텍스트는 쓰지 마라."
        )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 400,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.base_url.rstrip('/')}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
        except Exception as exc:
            print(f"[GrammarEvaluation] OpenAI 호출 실패(thread={thread_id}): {exc}")
            return {
                "grammar_score": None,
                "mistakes": [],
                "suggestions": [],
                "error": str(exc),
            }

        parsed = self._parse_llm_json(content)
        if not parsed:
            return {
                "grammar_score": None,
                "mistakes": [],
                "suggestions": [],
                "raw_response": content,
            }

        grammar_score = parsed.get("grammar_score") or parsed.get("score")
        try:
            grammar_score = self._clamp_score(float(grammar_score))
        except (TypeError, ValueError):
            grammar_score = None

        mistakes = parsed.get("mistakes") or parsed.get("errors") or []
        suggestions = parsed.get("suggestions") or parsed.get("recommendations") or []

        return {
            "grammar_score": grammar_score,
            "mistakes": mistakes,
            "suggestions": suggestions,
        }

    def _parse_llm_json(self, content: str) -> Optional[Dict[str, Any]]:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    return None
        return None

    @staticmethod
    def _clamp_score(value: Optional[float]) -> Optional[float]:
        if value is None:
            return None
        return max(0.0, min(100.0, float(value)))

    @staticmethod
    def _safe_float(value: Any) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _normalize_timestamp(value: Any) -> Optional[float]:
        raw = ScenarioService._safe_float(value)
        if raw is None:
            return None
        if raw >= 1000.0:
            return raw / 1000.0
        if raw > 30.0:
            return raw / 1000.0
        return raw

    @staticmethod
    def _compute_duration_variation_penalty(durations: List[float]) -> float:
        if not durations:
            return 0.0
        avg = sum(durations) / len(durations)
        variance = sum((d - avg) ** 2 for d in durations) / len(durations)
        std_dev = variance ** 0.5
        return min(10.0, std_dev * 25.0)

    @staticmethod
    def _normalize_duration(value: Any) -> Optional[float]:
        raw = ScenarioService._safe_float(value)
        if raw is None:
            return None
        if raw >= 1000.0:
            return raw / 1000.0
        if raw > 30.0:
            return raw / 1000.0
        return raw

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


