"""
사용자 관련 모델
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean, DECIMAL, Date
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class User(Base):
    """사용자 테이블"""
    __tablename__ = "users"
    
    user_id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password = Column(String(255), nullable=False)
    nickname = Column(String(45))
    profile_img = Column(String(500))
    nationality = Column(String(50))  # ISO 3166-1 alpha-2 코드
    job_id = Column(Integer, ForeignKey("jobs.job_id"))
    level_id = Column(Integer, ForeignKey("user_level.level_id"))
    theme = Column(String(20), default="light")  # 테마 설정 (light, dark, auto)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # 관계 설정
    job = relationship("Job", back_populates="users")
    level = relationship("UserLevel", back_populates="users")
    posts = relationship("Post", back_populates="user")
    replies = relationship("Reply", back_populates="user")
    user_progress = relationship("UserProgress", back_populates="user")
    sentence_progress = relationship("SentenceProgress", back_populates="user")
    chapter_feedback = relationship("ChapterFeedback", back_populates="user")
    sentence_feedback = relationship("SentenceFeedback", back_populates="user")
    scenario_progress = relationship("ScenarioProgress", back_populates="user")
    scenario_feedback = relationship("ScenarioFeedback", back_populates="user")
    user_status = relationship("UserStatus", back_populates="user", uselist=False)


class Job(Base):
    """직무 테이블"""
    __tablename__ = "jobs"
    
    job_id = Column(Integer, primary_key=True, index=True)
    job_name = Column(String(100), nullable=False, index=True)
    description = Column(Text)
    created_at = Column(DateTime, default=func.now())
    
    # 관계 설정
    users = relationship("User", back_populates="job")
    learning_categories = relationship("LearningCategory", back_populates="job")
    chapters = relationship("Chapter", back_populates="job")
    scenarios = relationship("Scenario", back_populates="job")


class UserLevel(Base):
    """사용자 레벨 테이블"""
    __tablename__ = "user_level"
    
    level_id = Column(Integer, primary_key=True, index=True)
    level_name = Column(String(20), nullable=False, index=True)  # 초급, 중급, 고급
    description = Column(Text)
    
    # 관계 설정
    users = relationship("User", back_populates="level")
    chapters = relationship("Chapter", back_populates="level")
    scenarios = relationship("Scenario", back_populates="level")


class UserStatus(Base):
    """사용자 상태 테이블"""
    __tablename__ = "user_status"
    
    status_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), unique=True, nullable=False)
    total_study_time = Column(Integer, default=0)  # 총 학습 시간 (분)
    total_sentences_completed = Column(Integer, default=0)  # 완료한 문장 수
    total_scenarios_completed = Column(Integer, default=0)  # 완료한 시나리오 수
    average_score = Column(DECIMAL(5, 2))  # 평균 점수
    current_access_days = Column(Integer, default=0)  # 연속 학습 일수
    longest_access_days = Column(Integer, default=0)  # 최장 연속 학습 일수
    last_study_date = Column(Date)  # 마지막 학습 날짜
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # 관계 설정
    user = relationship("User", back_populates="user_status")
