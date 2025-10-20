"""
학습 진행 관련 서비스
"""
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime
from decimal import Decimal

from app.models.progress import UserProgress, SentenceProgress
from app.models.learning import Chapter, Sentence
from app.schemas.progress import (
    UserProgressUpdate, SentenceProgressUpdate, ProgressStatsResponse,
    ChapterProgressResponse, UserProgressHistoryResponse
)


class ProgressService:
    def __init__(self, db: Session):
        self.db = db
    
    def get_user_progress_stats(self, user_id: int) -> Optional[ProgressStatsResponse]:
        """사용자 전체 학습 진행 현황 조회"""
        # 전체 챕터 수
        total_chapters = self.db.query(Chapter).filter(Chapter.is_active == True).count()
        
        # 완료한 챕터 수
        completed_chapters = self.db.query(UserProgress).filter(
            UserProgress.user_id == user_id,
            UserProgress.completion_rate >= 100
        ).count()
        
        # 전체 문장 수
        total_sentences = self.db.query(Sentence).join(Chapter).filter(
            Chapter.is_active == True
        ).count()
        
        # 완료한 문장 수
        completed_sentences = self.db.query(SentenceProgress).filter(
            SentenceProgress.user_id == user_id,
            SentenceProgress.is_completed == True
        ).count()
        
        # 전체 진행률 계산
        overall_progress = Decimal(0)
        if total_chapters > 0:
            overall_progress = (completed_chapters / total_chapters) * 100
        
        # 총 학습 시간 (분)
        study_time = self.db.query(UserProgress).filter(
            UserProgress.user_id == user_id
        ).with_entities(
            self.db.func.sum(UserProgress.completion_rate)
        ).scalar() or 0
        
        # 마지막 학습 날짜
        last_progress = self.db.query(UserProgress).filter(
            UserProgress.user_id == user_id
        ).order_by(UserProgress.last_access_at.desc()).first()
        
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
    
    def get_chapter_progress(self, chapter_id: int) -> Optional[ChapterProgressResponse]:
        """특정 챕터의 학습 진행률 조회"""
        chapter = self.db.query(Chapter).filter(Chapter.chapter_id == chapter_id).first()
        if not chapter:
            return None
        
        # 챕터 내 문장 수
        total_sentences = self.db.query(Sentence).filter(
            Sentence.chapter_id == chapter_id
        ).count()
        
        # 완료한 문장 수
        completed_sentences = self.db.query(SentenceProgress).join(Sentence).filter(
            Sentence.chapter_id == chapter_id,
            SentenceProgress.is_completed == True
        ).count()
        
        # 진행률 계산
        completion_rate = Decimal(0)
        if total_sentences > 0:
            completion_rate = (completed_sentences / total_sentences) * 100
        
        # 마지막 접근 시간
        last_progress = self.db.query(UserProgress).filter(
            UserProgress.chapter_id == chapter_id
        ).order_by(UserProgress.last_access_at.desc()).first()
        
        last_access_at = last_progress.last_access_at if last_progress else None
        
        return ChapterProgressResponse(
            chapter_id=chapter_id,
            chapter_title=chapter.title,
            completion_rate=completion_rate,
            total_sentences=total_sentences,
            completed_sentences=completed_sentences,
            last_access_at=last_access_at
        )
    
    def update_user_progress(
        self, 
        user_id: int, 
        chapter_id: int, 
        progress_update: UserProgressUpdate
    ) -> UserProgress:
        """사용자 진행률 업데이트"""
        progress = self.db.query(UserProgress).filter(
            UserProgress.user_id == user_id,
            UserProgress.chapter_id == chapter_id
        ).first()
        
        if not progress:
            progress = UserProgress(
                user_id=user_id,
                chapter_id=chapter_id,
                completion_rate=Decimal(0)
            )
            self.db.add(progress)
        
        update_data = progress_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(progress, field, value)
        
        progress.last_access_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(progress)
        
        return progress
    
    def get_sentence_progress(self, user_id: int, sentence_id: int) -> Optional[SentenceProgress]:
        """문장별 진행 상태 조회"""
        return self.db.query(SentenceProgress).filter(
            SentenceProgress.user_id == user_id,
            SentenceProgress.sentence_id == sentence_id
        ).first()
    
    def update_sentence_progress(
        self, 
        user_id: int, 
        sentence_id: int, 
        progress_update: SentenceProgressUpdate
    ) -> SentenceProgress:
        """문장 진행 상태 업데이트"""
        progress = self.get_sentence_progress(user_id, sentence_id)
        
        if not progress:
            progress = SentenceProgress(
                user_id=user_id,
                sentence_id=sentence_id,
                is_completed=False
            )
            self.db.add(progress)
        
        update_data = progress_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(progress, field, value)
        
        self.db.commit()
        self.db.refresh(progress)
        
        return progress
    
    def get_user_progress_history(self, user_id: int) -> Optional[UserProgressHistoryResponse]:
        """사용자 전체 학습 이력 조회"""
        # 챕터별 진행 현황
        chapter_progresses = self.db.query(UserProgress).filter(
            UserProgress.user_id == user_id
        ).join(Chapter).all()
        
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
        total_sentences_completed = self.db.query(SentenceProgress).filter(
            SentenceProgress.user_id == user_id,
            SentenceProgress.is_completed == True
        ).count()
        
        return UserProgressHistoryResponse(
            user_id=user_id,
            progress_history=progress_history,
            total_study_time=int(total_study_time),
            total_sentences_completed=total_sentences_completed,
            average_score=None  # 별도 계산 필요
        )
