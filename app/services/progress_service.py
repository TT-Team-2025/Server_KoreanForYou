"""
학습 진행 관련 서비스
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional, List
from datetime import datetime, timezone
from decimal import Decimal

from app.models.progress import UserProgress, SentenceProgress
from app.models.learning import Chapter, Sentence
from app.schemas.progress import (
    UserProgressUpdate, SentenceProgressUpdate, ProgressStatsResponse,
    ChapterProgressResponse, UserProgressHistoryResponse
)


class ProgressService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user_progress_stats(self, user_id: int) -> Optional[ProgressStatsResponse]:
        """사용자 전체 학습 진행 현황 조회"""
        # 전체 챕터 수
        total_chapters_result = await self.db.execute(
            select(func.count()).select_from(Chapter).where(Chapter.is_active == True)
        )
        total_chapters = total_chapters_result.scalar() or 0

        # 완료한 챕터 수
        completed_chapters_result = await self.db.execute(
            select(func.count()).select_from(UserProgress).where(
                UserProgress.user_id == user_id,
                UserProgress.completion_rate >= 100
            )
        )
        completed_chapters = completed_chapters_result.scalar() or 0

        # 전체 문장 수
        total_sentences_result = await self.db.execute(
            select(func.count()).select_from(Sentence).join(Chapter).where(
                Chapter.is_active == True
            )
        )
        total_sentences = total_sentences_result.scalar() or 0

        # 완료한 문장 수
        completed_sentences_result = await self.db.execute(
            select(func.count()).select_from(SentenceProgress).where(
                SentenceProgress.user_id == user_id,
                SentenceProgress.is_completed == True
            )
        )
        completed_sentences = completed_sentences_result.scalar() or 0

        # 전체 진행률 계산
        overall_progress = Decimal(0)
        if total_chapters > 0:
            overall_progress = (completed_chapters / total_chapters) * 100

        # 총 학습 시간 (분)
        study_time_result = await self.db.execute(
            select(func.sum(UserProgress.completion_rate)).where(
                UserProgress.user_id == user_id
            )
        )
        study_time = study_time_result.scalar() or 0

        # 마지막 학습 날짜
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
        """특정 챕터의 학습 진행률 조회"""
        chapter_result = await self.db.execute(
            select(Chapter).where(Chapter.chapter_id == chapter_id)
        )
        chapter = chapter_result.scalar_one_or_none()
        if not chapter:
            return None

        # 챕터 내 문장 수
        total_sentences_result = await self.db.execute(
            select(func.count()).select_from(Sentence).where(
                Sentence.chapter_id == chapter_id
            )
        )
        total_sentences = total_sentences_result.scalar() or 0

        # 완료한 문장 수
        completed_sentences_result = await self.db.execute(
            select(func.count()).select_from(SentenceProgress).join(Sentence).where(
                Sentence.chapter_id == chapter_id,
                SentenceProgress.is_completed == True
            )
        )
        completed_sentences = completed_sentences_result.scalar() or 0

        # 진행률 계산
        completion_rate = Decimal(0)
        if total_sentences > 0:
            completion_rate = (completed_sentences / total_sentences) * 100

        # 마지막 접근 시간
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
    
    async def update_user_progress(
        self,
        user_id: int,
        chapter_id: int,
        progress_update: UserProgressUpdate
    ) -> UserProgress:
        """사용자 진행률 업데이트"""
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

        update_data = progress_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(progress, field, value)

        progress.last_access_at = datetime.now(timezone.utc)
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
        progress_update: SentenceProgressUpdate
    ) -> SentenceProgress:
        """문장 진행 상태 업데이트"""
        progress = await self.get_sentence_progress(user_id, sentence_id)
        
        if not progress:
            progress = SentenceProgress(
                user_id=user_id,
                sentence_id=sentence_id,
                is_completed=False
            )
            self.db.add(progress)
        
        update_data = progress_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(progress, field, value)

        await self.db.commit()
        await self.db.refresh(progress)
        
        return progress
    
    async def get_user_progress_history(self, user_id: int) -> Optional[UserProgressHistoryResponse]:
        """사용자 전체 학습 이력 조회"""
        # 챕터별 진행 현황
        progresses_result = await self.db.execute(
            select(UserProgress).where(
                UserProgress.user_id == user_id
            ).join(Chapter)
        )
        chapter_progresses = list(progresses_result.scalars().all())
        
        progress_history = []
        for progress in chapter_progresses:
            chapter = progress.chapter
            progress_history.append(ChapterProgressResponse(
                chapter_id=chapter.chapter_id,
                chapter_title=chapter.title,
                completion_rate=progress.completion_rate,
                total_sentences=0,  # 별도 계산 필요
                completed_sentences=0,  # 별도 계산 필요
                last_access_at=progress.last_access_at
            ))
        
        # 전체 통계
        total_study_time = sum(p.completion_rate for p in chapter_progresses)
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
