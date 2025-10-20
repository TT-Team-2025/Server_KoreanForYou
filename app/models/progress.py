"""
학습 진행 상황 관련 모델
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Text, DECIMAL
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class UserProgress(Base):
    """사용자 진행 상황 테이블"""
    __tablename__ = "user_progress"
    
    progress_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    chapter_id = Column(Integer, ForeignKey("chapters.chapter_id"), nullable=False)
    completion_rate = Column(DECIMAL(5, 2), nullable=False, default=0)  # 0.00~100.00%
    last_access_at = Column(DateTime)
    created_at = Column(DateTime, default=func.now())
    
    # 관계 설정
    user = relationship("User", back_populates="user_progress")
    chapter = relationship("Chapter", back_populates="user_progress")


class SentenceProgress(Base):
    """문장 진행 상황 테이블"""
    __tablename__ = "sentence_progress"
    
    progress_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    sentence_id = Column(Integer, ForeignKey("sentences.sentence_id"), nullable=False)
    is_completed = Column(Boolean, default=False)
    
    # STT 관련
    stt_audio_url = Column(String(500))  # STT에 사용할 음성 파일 경로
    stt_transcript = Column(Text)  # STT로 변환된 텍스트
    
    # 통계
    total_word_count = Column(Integer)  # 전체 단어 수
    correct_word_count = Column(Integer)  # 맞은 단어 수
    recognized_word_count = Column(Integer)  # STT에서 인식된 단어 수
    
    # 시간
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    created_at = Column(DateTime, default=func.now())
    
    # 관계 설정
    user = relationship("User", back_populates="sentence_progress")
    sentence = relationship("Sentence", back_populates="sentence_progress")
    sentence_feedback = relationship("SentenceFeedback", back_populates="sentence_progress")
