"""
학습 진행 관련 서비스
"""
import asyncio
import re
from collections import Counter
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Tuple, Dict, Any

from fastapi import UploadFile
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.learning import Chapter, Sentence
from app.models.progress import UserProgress, SentenceProgress
from app.schemas.progress import (
    ProgressStatsResponse,
    ChapterProgressResponse, UserProgressHistoryResponse
)
from app.services.external_service import ExternalService


class ProgressService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user_progress_stats(self, user_id: int) -> Optional[ProgressStatsResponse]:
        """사용자 전체 학습 진행 현황 조회"""
        # 전체 활성 챕터 수
        total_chapters_result = await self.db.execute(
            select(func.count()).select_from(Chapter).where(Chapter.is_active == True)
        )
        total_chapters = total_chapters_result.scalar() or 0

        # 완료한 챕터 수 (100% 달성)
        completed_chapters_result = await self.db.execute(
            select(func.count()).select_from(UserProgress).where(
                UserProgress.user_id == user_id,
                UserProgress.completion_rate >= 100
            )
        )
        completed_chapters = completed_chapters_result.scalar() or 0

        # 전체 문장 수 (활성 챕터 기준)
        total_sentences_result = await self.db.execute(
            select(func.count()).select_from(Sentence).join(Chapter).where(
                Chapter.is_active == True
            )
        )
        total_sentences = total_sentences_result.scalar() or 0

        # 완료한 문장 수 (사용자 기준)
        completed_sentences_result = await self.db.execute(
            select(func.count()).select_from(SentenceProgress).where(
                SentenceProgress.user_id == user_id,
                SentenceProgress.is_completed == True
            )
        )
        completed_sentences = completed_sentences_result.scalar() or 0

        overall_progress = Decimal(0)
        if total_chapters > 0:
            overall_progress = (Decimal(completed_chapters) / Decimal(total_chapters)) * Decimal(100)
            overall_progress = overall_progress.quantize(Decimal("0.01"))

        # 총 학습 시간(분) - 임시로 completion_rate 합을 사용
        study_time_result = await self.db.execute(
            select(func.sum(UserProgress.completion_rate)).where(
                UserProgress.user_id == user_id
            )
        )
        study_time = study_time_result.scalar() or 0

        last_progress_result = await self.db.execute(
            select(UserProgress).where(
                UserProgress.user_id == user_id
            ).order_by(UserProgress.last_access_at.desc()).limit(1)
        )
        last_progress = last_progress_result.scalar_one_or_none()
        last_study_date = last_progress.last_access_at if last_progress else None

        return ProgressStatsResponse(
            total_chapters=total_chapters,
            completed_chapters=completed_chapters,
            total_sentences=total_sentences,
            completed_sentences=completed_sentences,
            overall_progress=overall_progress,
            study_time_minutes=int(study_time),
            last_study_date=last_study_date
        )

    async def get_chapter_progress(self, chapter_id: int) -> Optional[ChapterProgressResponse]:
        """특정 챕터의 전체 학습 진행률 조회"""
        chapter_result = await self.db.execute(
            select(Chapter).where(Chapter.chapter_id == chapter_id)
        )
        chapter = chapter_result.scalar_one_or_none()
        if not chapter:
            return None

        total_sentences_result = await self.db.execute(
            select(func.count()).select_from(Sentence).where(
                Sentence.chapter_id == chapter_id
            )
        )
        total_sentences = total_sentences_result.scalar() or 0

        completed_sentences_result = await self.db.execute(
            select(func.count()).select_from(SentenceProgress).join(Sentence).where(
                Sentence.chapter_id == chapter_id,
                SentenceProgress.is_completed == True
            )
        )
        completed_sentences = completed_sentences_result.scalar() or 0

        completion_rate = Decimal(0)
        if total_sentences > 0:
            completion_rate = (Decimal(completed_sentences) / Decimal(total_sentences)) * Decimal(100)
            completion_rate = completion_rate.quantize(Decimal("0.01"))

        last_progress_result = await self.db.execute(
            select(UserProgress).where(
                UserProgress.chapter_id == chapter_id
            ).order_by(UserProgress.last_access_at.desc()).limit(1)
        )
        last_progress = last_progress_result.scalar_one_or_none()
        last_access_at = last_progress.last_access_at if last_progress else None

        return ChapterProgressResponse(
            chapter_id=chapter_id,
            chapter_title=chapter.title,
            completion_rate=completion_rate,
            total_sentences=total_sentences,
            completed_sentences=completed_sentences,
            last_access_at=last_access_at
        )

#챕터 진행룰 계산
    async def _compute_chapter_completion(
        self,
        user_id: int,
        chapter_id: int
    ) -> Tuple[Decimal, int, int]:
        """챕터 전체 문장 대비 완료 문장 비율 계산"""
        total_sentences_result = await self.db.execute(
            select(func.count()).select_from(Sentence).where(
                Sentence.chapter_id == chapter_id
            )
        )
        total_sentences = total_sentences_result.scalar() or 0

        completed_sentences_result = await self.db.execute(
            select(func.count())
            .select_from(SentenceProgress)
            .join(Sentence, SentenceProgress.sentence_id == Sentence.sentence_id)
            .where(
                SentenceProgress.user_id == user_id,
                SentenceProgress.is_completed == True,
                Sentence.chapter_id == chapter_id
            )
        )
        completed_sentences = completed_sentences_result.scalar() or 0

        completion_rate = Decimal(0)
        if total_sentences > 0:
            completion_rate = (
                Decimal(completed_sentences) / Decimal(total_sentences)
            ) * Decimal(100)
            completion_rate = completion_rate.quantize(Decimal("0.01"))

        return completion_rate, total_sentences, completed_sentences
    
    async def update_user_progress(
        self,
        user_id: int,
        chapter_id: int
    ) -> UserProgress:
        """사용자 진행률을 실제 완료 문장 비율 기반으로 업데이트"""
        progress_result = await self.db.execute(
            select(UserProgress).where(
                UserProgress.user_id == user_id,
                UserProgress.chapter_id == chapter_id
            )
        )
        progress = progress_result.scalar_one_or_none()

        if not progress:
            progress = UserProgress(
                user_id=user_id,
                chapter_id=chapter_id,
                completion_rate=Decimal(0)
            )
            self.db.add(progress)

        completion_rate, _, _ = await self._compute_chapter_completion(user_id, chapter_id)
        progress.completion_rate = completion_rate
        progress.last_access_at = datetime.now()
        await self.db.commit()
        await self.db.refresh(progress)
        
        return progress
    
    async def get_sentence_progress(self, user_id: int, sentence_id: int) -> Optional[SentenceProgress]:
        """문장별 진행 상태 조회"""
        result = await self.db.execute(
            select(SentenceProgress).where(
                SentenceProgress.user_id == user_id,
                SentenceProgress.sentence_id == sentence_id
            )
        )
        return result.scalar_one_or_none()
    




    
    async def update_sentence_progress(
        self,
        user_id: int,
        sentence_id: int,
        audio_file: UploadFile
    ) -> Tuple[SentenceProgress, Dict[str, List[str]]]:
        """문장 진행 상태 업데이트(STT 기반)"""
        sentence_result = await self.db.execute(
            select(Sentence).where(Sentence.sentence_id == sentence_id)
        )
        sentence = sentence_result.scalar_one_or_none()

        if not sentence:
            raise ValueError("문장을 찾을 수 없습니다.")

        progress = await self.get_sentence_progress(user_id, sentence_id)
        if not progress:
            progress = SentenceProgress(
                user_id=user_id,
                sentence_id=sentence_id,
                is_completed=False
            )
            self.db.add(progress)

        external_service = ExternalService(self.db)
        config = {
            "model_name": "sommers",
            "language": "ko",
            "use_itn": True,
            "use_disfluency_filter": True,
            "use_profanity_filter": False,
            "use_paragraph_splitter": True,
            "use_word_timestamp": True,
        }

        session_start = datetime.now()

        try:
            await audio_file.seek(0)
            stt_initial_result = await external_service.transcribe_file(audio_file, config)
            transcribe_id = stt_initial_result.get("id")
            if not transcribe_id:
                raise RuntimeError("전사 ID를 받지 못했습니다.")

            final_result = await asyncio.to_thread(
                external_service.rtzr_client.wait_for_result,
                transcribe_id,
                5,
                3600
            )

            if final_result.get("status") != "completed":
                error_message = final_result.get("message", "전사 실패")
                raise RuntimeError(f"전사 실패: {error_message}")

            results = final_result.get("results") or {}
            utterances = results.get("utterances", []) if isinstance(results, dict) else []
            transcript_segments: List[str] = []
            recognized_words: List[str] = []
            word_timestamps: List[str] = []
            raw_utterances: List[Dict[str, Any]] = []

            for utterance in utterances:
                msg = utterance.get("msg") or utterance.get("text") or ""
                if msg:
                    transcript_segments.append(msg)
                raw_utterances.append(utterance)
                for word_info in utterance.get("words", []):
                    word_text = (
                        word_info.get("msg")
                        or word_info.get("text")
                        or word_info.get("word")
                    )
                    if word_text:
                        recognized_words.append(word_text)
                        word_timestamps.append(word_text)

            stt_transcript = " ".join(transcript_segments).strip()
            if not stt_transcript:
                stt_transcript = " ".join(recognized_words).strip()

            if not stt_transcript:
                raise RuntimeError("전사된 텍스트가 비어 있습니다.")

            def tokenize(text: str) -> List[str]:
                tokens: List[str] = []
                for raw in text.split():
                    cleaned = re.sub(r"[^\w가-힣]", "", raw).lower()
                    if cleaned:
                        tokens.append(cleaned)
                return tokens

            target_tokens = tokenize(sentence.content or "")
            recognized_tokens = tokenize(" ".join(recognized_words) or stt_transcript)

            total_word_count = len(target_tokens)
            recognized_word_count = len(recognized_tokens)

            target_counter = Counter(target_tokens)
            recognized_counter = Counter(recognized_tokens)
            correct_word_count = sum(
                min(target_counter[word], recognized_counter.get(word, 0))
                for word in target_counter
            )

            missing_words: List[str] = []
            for word, count in target_counter.items():
                remaining = count - min(count, recognized_counter.get(word, 0))
                if remaining > 0:
                    missing_words.extend([word] * remaining)

            extra_words: List[str] = []
            for word, count in recognized_counter.items():
                overflow = count - target_counter.get(word, 0)
                if overflow > 0:
                    extra_words.extend([word] * overflow)

            progress.stt_transcript = stt_transcript
            progress.word_timestamps = word_timestamps or None
            progress.total_word_count = total_word_count
            progress.recognized_word_count = recognized_word_count
            progress.correct_word_count = correct_word_count
            if not progress.start_time:
                progress.start_time = session_start
            progress.end_time = None
            progress.total_time = None
            progress.is_completed = total_word_count > 0 and correct_word_count == total_word_count

            completion_rate, _, _ = await self._compute_chapter_completion(user_id, sentence.chapter_id)
            chapter_progress_result = await self.db.execute(
                select(UserProgress).where(
                    UserProgress.user_id == user_id,
                    UserProgress.chapter_id == sentence.chapter_id
                )
            )
            chapter_progress = chapter_progress_result.scalar_one_or_none()
            if not chapter_progress:
                chapter_progress = UserProgress(
                    user_id=user_id,
                    chapter_id=sentence.chapter_id,
                )
                self.db.add(chapter_progress)
            chapter_progress.completion_rate = completion_rate
            chapter_progress.last_access_at = datetime.now()

            mismatch_info = {
                "missing_words": missing_words,
                "extra_words": extra_words,
                "raw_utterances": raw_utterances,
            }
        finally:
            await audio_file.close()

        await self.db.commit()
        await self.db.refresh(progress)

        return progress, mismatch_info
    
    async def get_user_progress_history(self, user_id: int) -> Optional[UserProgressHistoryResponse]:
        """사용자 전체 학습 이력 조회"""
        progresses_result = await self.db.execute(
            select(UserProgress)
            .where(UserProgress.user_id == user_id)
            .options(selectinload(UserProgress.chapter))
        )
        chapter_progresses = list(progresses_result.scalars().all())

        progress_history: List[ChapterProgressResponse] = []
        for progress in chapter_progresses:
            chapter = progress.chapter
            completion_rate, total_sentences, completed_sentences = await self._compute_chapter_completion(
                user_id, chapter.chapter_id
            )
            progress_history.append(ChapterProgressResponse(
                chapter_id=chapter.chapter_id,
                chapter_title=chapter.title,
                completion_rate=completion_rate,
                total_sentences=total_sentences,
                completed_sentences=completed_sentences,
                last_access_at=progress.last_access_at
            ))

        total_study_time = sum(float(p.completion_rate) for p in chapter_progresses)
        completed_result = await self.db.execute(
            select(func.count()).select_from(SentenceProgress).where(
                SentenceProgress.user_id == user_id,
                SentenceProgress.is_completed == True
            )
        )
        total_sentences_completed = completed_result.scalar() or 0

        return UserProgressHistoryResponse(
            user_id=user_id,
            progress_history=progress_history,
            total_study_time=int(total_study_time),
            total_sentences_completed=total_sentences_completed,
            average_score=None  # 별도 계산 필요
        )
    
 
