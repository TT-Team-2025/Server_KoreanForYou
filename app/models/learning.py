"""
학습 콘텐츠 관련 모델
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class LearningCategory(Base):
    """학습 카테고리 테이블"""
    __tablename__ = "learning_categories"
    
    category_id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.job_id"), nullable=False)
    title = Column(String(150), nullable=False)
    sub_title = Column(String(150), default="모든 직무 공통")
    
    # 관계 설정
    job = relationship("Job", back_populates="learning_categories")
    chapters = relationship("Chapter", back_populates="category")


class Chapter(Base):
    """챕터 테이블"""
    __tablename__ = "chapters"
    
    chapter_id = Column(Integer, primary_key=True, index=True)
    category_id = Column(Integer, ForeignKey("learning_categories.category_id"), nullable=False)
    job_id = Column(Integer, ForeignKey("jobs.job_id"))  # 0이면 공통 챕터
    level_id = Column(Integer, ForeignKey("user_level.level_id"), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    
    # 관계 설정
    category = relationship("LearningCategory", back_populates="chapters")
    job = relationship("Job", back_populates="chapters")
    level = relationship("UserLevel", back_populates="chapters")
    sentences = relationship("Sentence", back_populates="chapter")
    chapter_feedback = relationship("ChapterFeedback", back_populates="chapter")
    user_progress = relationship("UserProgress", back_populates="chapter")


class Sentence(Base):
    """문장 테이블"""
    __tablename__ = "sentences"
    
    sentence_id = Column(Integer, primary_key=True, index=True)
    chapter_id = Column(Integer, ForeignKey("chapters.chapter_id"), nullable=False)
    content = Column(String(500), nullable=False)
    translated_content = Column(String(500))
    tts_url = Column(String(500))  # TTS 오디오 파일 경로
    created_at = Column(DateTime, default=func.now())
    
    # 관계 설정
    chapter = relationship("Chapter", back_populates="sentences")
    similar_sentences = relationship("SimilarSentence", back_populates="sentence")
    sentence_progress = relationship("SentenceProgress", back_populates="sentence")
    sentence_feedback = relationship("SentenceFeedback", back_populates="sentence")


class SimilarSentence(Base):
    """유사 문장 테이블"""
    __tablename__ = "similar_sentences"
    
    similar_sentence_id = Column(Integer, primary_key=True, index=True)
    sentence_id = Column(Integer, ForeignKey("sentences.sentence_id"), nullable=False)
    content = Column(String(500), nullable=False)
    translated_content = Column(String(500))
    similarity_type = Column(String(20))  # 동의어, 유사표현, 난이도조정, 상황변형
    created_at = Column(DateTime, default=func.now())
    
    # 관계 설정
    sentence = relationship("Sentence", back_populates="similar_sentences")


class ChapterFeedback(Base):
    """챕터 피드백 테이블"""
    __tablename__ = "chapter_feedback"
    
    feedback_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    chapter_id = Column(Integer, ForeignKey("chapters.chapter_id"), nullable=False)
    
    # 종합 평가 점수
    total_score = Column(Integer)  # 0-100
    pronunciation_score = Column(Integer)  # 0-100
    accuracy_score = Column(Integer)  # 0-100
    completion_time = Column(Integer)  # 완료 소요 시간 (분)
    
    # 문장별 성취도
    total_sentences = Column(Integer, nullable=False)
    completed_sentences = Column(Integer, nullable=False)
    
    # AI 종합 피드백
    summary_feedback = Column(Text)
    weaknesses = Column(JSON)  # 개선이 필요한 부분 (JSON 배열)
    
    # 시간 기록
    total_time = Column(Integer)  # 총 학습 시간 (초)
    created_at = Column(DateTime, default=func.now())
    
    # 관계 설정
    user = relationship("User", back_populates="chapter_feedback")
    chapter = relationship("Chapter", back_populates="chapter_feedback")


class SentenceFeedback(Base):
    """문장 피드백 테이블"""
    __tablename__ = "sentence_feedback"
    
    feedback_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    sentence_id = Column(Integer, ForeignKey("sentences.sentence_id"), nullable=False)
    sentence_progress_id = Column(Integer, ForeignKey("sentence_progress.progress_id"), nullable=False)
    weaknesses = Column(JSON)  # 개선이 필요한 부분 (JSON 배열)
    
    # 관계 설정
    user = relationship("User", back_populates="sentence_feedback")
    sentence = relationship("Sentence", back_populates="sentence_feedback")
    sentence_progress = relationship("SentenceProgress", back_populates="sentence_feedback")
