"""
피드백 관련 서비스
"""
from sqlalchemy.orm import Session
from typing import Optional

from app.models.learning import ChapterFeedback, SentenceFeedback
from app.models.scenario import ScenarioFeedback
from app.schemas.learning import ChapterFeedbackCreate, SentenceFeedbackCreate


class FeedbackService:
    def __init__(self, db: Session):
        self.db = db
    
    def get_chapter_feedback(self, user_id: int, chapter_id: int) -> Optional[ChapterFeedback]:
        """챕터 피드백 조회"""
        return self.db.query(ChapterFeedback).filter(
            ChapterFeedback.user_id == user_id,
            ChapterFeedback.chapter_id == chapter_id
        ).first()
    
    def save_chapter_feedback(
        self, 
        user_id: int, 
        chapter_id: int, 
        feedback_data: ChapterFeedbackCreate
    ) -> ChapterFeedback:
        """챕터 피드백 저장"""
        # 기존 피드백이 있으면 업데이트, 없으면 생성
        feedback = self.get_chapter_feedback(user_id, chapter_id)
        
        if feedback:
            # 업데이트
            update_data = feedback_data.dict(exclude_unset=True)
            for field, value in update_data.items():
                setattr(feedback, field, value)
        else:
            # 생성
            feedback = ChapterFeedback(
                user_id=user_id,
                chapter_id=chapter_id,
                **feedback_data.dict()
            )
            self.db.add(feedback)
        
        self.db.commit()
        self.db.refresh(feedback)
        
        return feedback
    
    def get_sentence_feedback(self, user_id: int, sentence_id: int) -> Optional[SentenceFeedback]:
        """문장 피드백 조회"""
        return self.db.query(SentenceFeedback).filter(
            SentenceFeedback.user_id == user_id,
            SentenceFeedback.sentence_id == sentence_id
        ).first()
    
    def save_sentence_feedback(
        self, 
        user_id: int, 
        sentence_id: int, 
        feedback_data: SentenceFeedbackCreate
    ) -> SentenceFeedback:
        """문장 피드백 저장"""
        # 기존 피드백이 있으면 업데이트, 없으면 생성
        feedback = self.get_sentence_feedback(user_id, sentence_id)
        
        if feedback:
            # 업데이트
            update_data = feedback_data.dict(exclude_unset=True)
            for field, value in update_data.items():
                setattr(feedback, field, value)
        else:
            # 생성
            feedback = SentenceFeedback(
                user_id=user_id,
                sentence_id=sentence_id,
                **feedback_data.dict()
            )
            self.db.add(feedback)
        
        self.db.commit()
        self.db.refresh(feedback)
        
        return feedback
    
    def get_scenario_feedback(self, user_id: int, scenario_id: int) -> Optional[ScenarioFeedback]:
        """시나리오 피드백 조회"""
        # 시나리오 진행 상황에서 최근 피드백 조회
        from app.models.scenario import ScenarioProgress
        
        progress = self.db.query(ScenarioProgress).filter(
            ScenarioProgress.user_id == user_id,
            ScenarioProgress.scenario_id == scenario_id
        ).order_by(ScenarioProgress.start_time.desc()).first()
        
        if not progress:
            return None
        
        return self.db.query(ScenarioFeedback).filter(
            ScenarioFeedback.log_id == progress.progress_id
        ).first()
