"""
시나리오 관련 모델
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
import enum


class CompletionStatus(str, enum.Enum):
    """완료 상태"""
    IN_PROGRESS = "진행중"
    COMPLETED = "완료"
    CANCELLED = "중단"


class Scenario(Base):
    """시나리오 테이블"""
    __tablename__ = "scenarios"
    
    scenario_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"))
    title = Column(String(200), nullable=False)
    description = Column(Text)
    job_id = Column(Integer, ForeignKey("jobs.job_id"))
    level_id = Column(Integer, ForeignKey("user_level.level_id"))
    created_at = Column(DateTime, default=func.now())
    
    # 관계 설정
    user = relationship("User")
    job = relationship("Job", back_populates="scenarios")
    level = relationship("UserLevel", back_populates="scenarios")
    scenario_progress = relationship("ScenarioProgress", back_populates="scenario")


class Role(Base):
    """역할 테이블"""
    __tablename__ = "roles"
    
    role_id = Column(Integer, primary_key=True, index=True)
    role_name = Column(String(50), nullable=False)
    description = Column(Text)
    
    # 관계 설정
    user_scenario_progress = relationship("ScenarioProgress", foreign_keys="ScenarioProgress.user_role_id")
    ai_scenario_progress = relationship("ScenarioProgress", foreign_keys="ScenarioProgress.ai_role_id")


class ScenarioProgress(Base):
    """시나리오 진행 상황 테이블"""
    __tablename__ = "scenario_progress"
    
    progress_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    scenario_id = Column(Integer, ForeignKey("scenarios.scenario_id"), nullable=False)
    user_role_id = Column(Integer, ForeignKey("roles.role_id"), nullable=False)
    ai_role_id = Column(Integer, ForeignKey("roles.role_id"), nullable=False)
    
    turn_count = Column(Integer)  # 발화 횟수
    description = Column(Text)  # 상황 설명
    conversation = Column(JSON)  # 대화 내역 (JSON 형태)
    
    start_time = Column(DateTime, nullable=False, default=func.now())
    end_time = Column(DateTime)
    completion_status = Column(Enum(CompletionStatus), nullable=False, default=CompletionStatus.IN_PROGRESS)
    
    # 관계 설정
    user = relationship("User", back_populates="scenario_progress")
    scenario = relationship("Scenario", back_populates="scenario_progress")
    user_role = relationship("Role", foreign_keys=[user_role_id])
    ai_role = relationship("Role", foreign_keys=[ai_role_id])
    scenario_feedback = relationship("ScenarioFeedback", back_populates="scenario_progress")


class ScenarioFeedback(Base):
    """시나리오 피드백 테이블"""
    __tablename__ = "scenario_feedback"
    
    feedback_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"))
    log_id = Column(Integer, ForeignKey("scenario_progress.progress_id"), unique=True, nullable=False)
    
    # 평가 점수
    pronunciation_score = Column(Integer)  # 0-100
    accuracy_score = Column(Integer)  # 0-100
    fluency_score = Column(Integer)  # 0-100
    completeness_score = Column(Integer)  # 0-100
    total_score = Column(Integer)  # 0-100
    
    # AI 피드백
    comment = Column(Text)  # AI 피드백 코멘트
    detail_comment = Column(JSON)  # 개선 제안 사항 (JSON 배열)
    
    created_at = Column(DateTime, default=func.now())
    
    # 관계 설정
    user = relationship("User", back_populates="scenario_feedback")
    scenario_progress = relationship("ScenarioProgress", back_populates="scenario_feedback")
