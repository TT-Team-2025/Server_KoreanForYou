"""
학습 진행 관련 서비스
"""
import asyncio
import re
from collections import Counter
from datetime import datetime, timezone
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
    ChapterProgressResponse,
    UserProgressHistoryResponse,
)
from app.services.external_service import ExternalService


class ProgressService:
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _safe_float(value: Any) -> Optional[float]:
        """안전하게 float로 변환"""
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _normalize_timestamp(value: Any) -> Optional[float]:
        """타임스탬프를 초 단위로 정규화 (밀리초인 경우 변환)"""
        raw = ProgressService._safe_float(value)
        if raw is None:
            return None
        if raw >= 1000.0:
            return raw / 1000.0
        if raw > 30.0:
            return raw / 1000.0
        return raw

    @staticmethod
    def _normalize_duration(value: Any) -> Optional[float]:
        """지속 시간을 초 단위로 정규화 (밀리초인 경우 변환)"""
        raw = ProgressService._safe_float(value)
        if raw is None:
            return None
        if raw >= 1000.0:
            return raw / 1000.0
        if raw > 30.0:
            return raw / 1000.0
        return raw

    @staticmethod
    def _clamp_score(value: Optional[float]) -> Optional[float]:
        """점수를 0.0~100.0 범위로 제한"""
        if value is None:
            return None
        return max(0.0, min(100.0, float(value)))

    @staticmethod
    def _compute_duration_variation_penalty(durations: List[float]) -> float:
        """지속 시간 변동성에 대한 패널티 계산"""
        if not durations:
            return 0.0
        avg = sum(durations) / len(durations)
        variance = sum((d - avg) ** 2 for d in durations) / len(durations)
        std_dev = variance ** 0.5
        return min(10.0, std_dev * 25.0)

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

    def _calculate_pronunciation_metrics(
        self,
        words: List[Dict[str, Any]],
        utterances: List[Dict[str, Any]],
    ) -> Tuple[Optional[float], Dict[str, Any]]:
        """발음 점수 계산 (타임스탬프 기반)"""
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
    
    async def update_sentence_progress(
        self,
        user_id: int,
        sentence_id: int,
        start_time: datetime,
        audio_file: UploadFile
    ) -> Tuple[SentenceProgress, Dict[str, Any]]:
        """문장 진행 상태 업데이트(STT 기반)"""
        # ✅ start_time을 timezone-naive UTC로 정규화 (DB 호환성)
        if start_time.tzinfo is None:
            # 이미 timezone-naive면 그대로 사용
            pass
        else:
            # timezone-aware면 UTC로 변환 후 tzinfo 제거
            start_time = start_time.astimezone(timezone.utc).replace(tzinfo=None)

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
            "use_disfluency_filter": False,
            "use_profanity_filter": False,
            "use_paragraph_splitter": True,
            "use_word_timestamp": True,
        }

        # ✅ session_start도 timezone-naive UTC로 (DB 호환성)
        session_start = datetime.now(timezone.utc).replace(tzinfo=None)

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
            word_timestamps: List[Dict[str, Any]] = []
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
                    if not word_text:
                        continue
                    
                    recognized_words.append(word_text)
                    
                    # 타임스탬프 정보 추출
                    start = self._normalize_timestamp(
                        word_info.get("start_at")
                        or word_info.get("start")
                        or word_info.get("begin_at")
                    )
                    end = self._normalize_timestamp(
                        word_info.get("end_at")
                        or word_info.get("end")
                        or word_info.get("finish_at")
                    )
                    duration = self._normalize_duration(
                        word_info.get("duration") or word_info.get("duration_ms")
                    )
                    confidence = self._safe_float(
                        word_info.get("confidence") or word_info.get("score")
                    )
                    
                    # utterance 레벨에서 보완
                    if start is None and utterance.get("start_at") is not None:
                        start = self._normalize_timestamp(utterance.get("start_at"))
                    if end is None and utterance.get("end_at") is not None:
                        end = self._normalize_timestamp(utterance.get("end_at"))
                    if duration is None and utterance.get("duration") is not None:
                        duration = self._normalize_duration(utterance.get("duration"))
                    
                    # 계산으로 보완
                    if end is None and start is not None and duration is not None:
                        end = start + duration
                    if start is None and end is not None and duration is not None:
                        start = end - duration
                    if duration is None and start is not None and end is not None:
                        duration = max(0.0, end - start)
                    
                    word_timestamps.append({
                        "text": word_text,
                        "start": start,
                        "end": end,
                        "duration": duration,
                        "confidence": confidence,
                    })

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

            # 발음 점수 계산 (타임스탬프 기반)
            pronunciation_score, pronunciation_detail = self._calculate_pronunciation_metrics(
                word_timestamps, utterances
            )

            # 정확도 점수 계산
            accuracy_score = None
            if total_word_count > 0:
                accuracy_score = (Decimal(correct_word_count) / Decimal(total_word_count)) * Decimal(100)
                accuracy_score = accuracy_score.quantize(Decimal("0.01"))

            # 전체 점수 계산 (발음 점수와 정확도 점수의 평균)
            overall_score = None
            if pronunciation_score is not None and accuracy_score is not None:
                overall_score = (Decimal(str(pronunciation_score)) + accuracy_score) / Decimal(2)
                overall_score = overall_score.quantize(Decimal("0.01"))
            elif pronunciation_score is not None:
                overall_score = Decimal(str(pronunciation_score)).quantize(Decimal("0.01"))
            elif accuracy_score is not None:
                overall_score = accuracy_score

            progress.stt_transcript = stt_transcript
            progress.word_timestamps = word_timestamps or None
            progress.total_word_count = total_word_count
            progress.recognized_word_count = recognized_word_count
            progress.correct_word_count = correct_word_count
            progress.start_time = start_time
            progress.end_time = session_start
            progress.total_time = (session_start-start_time).seconds
            progress.is_completed = total_word_count > 0

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
                "target_sentence": sentence.content,  # 원본 문장
                "missing_words": missing_words,
                "extra_words": extra_words,
                "raw_utterances": raw_utterances,
                "pronunciation_score": pronunciation_score,
                "pronunciation_detail": pronunciation_detail,
                "accuracy_score": float(accuracy_score) if accuracy_score is not None else None,
                "overall_score": float(overall_score) if overall_score is not None else None,
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

    async def user_chapter_progress(self, user_id: int, chapter_id: int) -> int:
        """특정 사용자의 특정 챕터 완료율 조회 (0-100 정수)"""
        completion_rate, _, _ = await self._compute_chapter_completion(user_id, chapter_id)
        return int(completion_rate)