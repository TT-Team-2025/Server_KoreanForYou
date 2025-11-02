"""
피드백 관련 서비스
"""
from sqlalchemy.orm import Session
from typing import Optional

from app.models.learning import ChapterFeedback, SentenceFeedback
from app.models.scenario import ScenarioFeedback
from app.schemas.learning import ChapterFeedbackCreate, SentenceFeedbackCreate
from app.services.llm_service import llm_service
from app.models.progress import SentenceProgress

## 매개변수 수정 필요 -> FeedbackCreate!

class FeedbackService:
    def __init__(self, db: Session):
        self.db = db
    
    def get_chapter_feedback(self, user_id: int, chapter_id: int) -> Optional[ChapterFeedback]:
        """챕터 피드백 조회"""
        return self.db.query(ChapterFeedback).filter(
            ChapterFeedback.user_id == user_id,
            ChapterFeedback.chapter_id == chapter_id
        ).first()


    def generarte_chapter_feedback(
        self, 
        user_id: int, 
        chapter_id: int, 
    ) -> ChapterFeedback:
        """챕터 피드백 생성 및 저장"""
        # 무조곤 생성하는 로직으로 변경
        ## 문장 학습을 도중에 중단했을 경우도 추후 고려 필요
        
        # 문장 피드백 조회
        sentence_feedbacks = self.db.query(SentenceFeedback).filter(
            SentenceFeedback.user_id == user_id,
            SentenceFeedback.sentence.chapter_id == chapter_id
        ).all()
        
        # 문장 id 조회
        sentence_ids = [fb.sentencd_id for fb in sentence_feedbacks]
        
        # 문장 진행사항 조회
        sentences_progresses = self.db.query(SentenceProgress).filter(
            SentenceProgress.sentence_id.in_(sentence_ids),
            SentenceProgress.user_id == user_id
        ).all()
        
        ## 종합 평가, 문장별 성취도, ai 종합 피드백, 시간 기록
        
        pronunciation_score = sum(
            st.correct_word_count / st.total_word_count * 100
            for st in sentences_progresses 
            if st.total_word_count and st.correct_word_count
        )
        
        accuracy_score = sum(
            st.recognized_word_count / st.total_word_count * 100
            for st in sentences_progresses 
            if st.total_word_count and st.recognized_word_count
        )
        
        weaknesses = self.db.query(SentenceFeedback.weaknesses).filter(
            SentenceFeedback.user_id == user_id,
            SentenceFeedback.sentence.chapter_id == chapter_id
        ).all()
        
        # llm 서비스 연동 필요
        summary_feedback = llm_service.generate_chapter_summary_feedback(
            weaknesses
        )
        
        # fleuncy_score = sum(
        #     (int)st.start_time - (int)st.end_time
        #     for st in sentences_progresses
        #     if st.start_time and st.end_time
        # )        
        
        # 생성
        feedback = ChapterFeedback(
            user_id=user_id,
            chapter_id=chapter_id,
            
            total_score=(pronunciation_score + accuracy_score) // 2,
            pronunciation_score=pronunciation_score,
            accuracy_score=accuracy_score,
            summary_feedback=summary_feedback,
            weaknesses=[w for sublist in weaknesses for w in sublist],
            completion_time=sentences_progresses[-1].end_time,
            total_time=(sentences_progresses[0].start_time - sentences_progresses[-1].end_tim).total_seconds() / 60,
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
    

    def generate_sentence_feedback(
        self, 
        user_id: int, 
        sentence_id: int, 
        sentence_progress_id: int
    ) -> SentenceFeedback:
        """문장 피드백 생성"""

        # 생성
        feedback = SentenceFeedback(
            user_id=user_id,
            sentence_id=sentence_id,
            sentence_progress_id=sentence_progress_id
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
    
    ## 시나리오 피드백 생성 로직 - 구현중
    def generate_scenario_feedback(
        self, 
        log_id: int, 
        feedback_data: dict
    ) -> ScenarioFeedback:
        """시나리오 피드백 생성"""
        feedback = ScenarioFeedback(
            log_id=log_id,
            **feedback_data
        )
        self.db.add(feedback)
        self.db.commit()
        self.db.refresh(feedback)
        
        return feedback
