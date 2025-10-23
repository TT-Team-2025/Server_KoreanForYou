"""
시나리오 관련 스키마
"""
from pydantic import BaseModel, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class CompletionStatus(str, Enum):
    IN_PROGRESS = "진행중"
    COMPLETED = "완료"
    CANCELLED = "중단"


# 시나리오 관련
class ScenarioBase(BaseModel):
    title: str
    description: Optional[str] = None
    job_id: Optional[int] = None
    level_id: Optional[int] = None
    
    @validator('title')
    def validate_title(cls, v):
        if len(v) < 1 or len(v) > 200:
            raise ValueError('제목은 1-200자 사이여야 합니다 commit 테스트')
        return v


class ScenarioCreate(ScenarioBase):
    pass


class ScenarioUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    job_id: Optional[int] = None
    level_id: Optional[int] = None
    
    @validator('title')
    def validate_title(cls, v):
        if v is not None and (len(v) < 1 or len(v) > 200):
            raise ValueError('제목은 1-200자 사이여야 합니다')
        return v


class ScenarioResponse(ScenarioBase):
    scenario_id: int
    user_id: Optional[int] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class ScenarioListResponse(BaseModel):
    scenarios: List[ScenarioResponse]
    total: int
    page: int
    size: int


# 역할 관련
class RoleBase(BaseModel):
    role_name: str
    description: Optional[str] = None


class RoleCreate(RoleBase):
    pass


class RoleResponse(RoleBase):
    role_id: int
    
    class Config:
        from_attributes = True


# 시나리오 진행 상황 관련
class ScenarioProgressBase(BaseModel):
    user_id: int
    scenario_id: int
    user_role_id: int
    ai_role_id: int
    turn_count: Optional[int] = None
    description: Optional[str] = None
    conversation: Optional[List[Dict[str, Any]]] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    completion_status: CompletionStatus = CompletionStatus.IN_PROGRESS


class ScenarioProgressCreate(ScenarioProgressBase):
    pass


class ScenarioProgressUpdate(BaseModel):
    turn_count: Optional[int] = None
    description: Optional[str] = None
    conversation: Optional[List[Dict[str, Any]]] = None
    end_time: Optional[datetime] = None
    completion_status: Optional[CompletionStatus] = None


class ScenarioProgressResponse(ScenarioProgressBase):
    progress_id: int
    
    class Config:
        from_attributes = True


# 시나리오 피드백 관련
class ScenarioFeedbackBase(BaseModel):
    user_id: int
    log_id: int
    pronunciation_score: Optional[int] = None
    accuracy_score: Optional[int] = None
    fluency_score: Optional[int] = None
    completeness_score: Optional[int] = None
    total_score: Optional[int] = None
    comment: Optional[str] = None
    detail_comment: Optional[List[str]] = None


class ScenarioFeedbackCreate(ScenarioFeedbackBase):
    pass


class ScenarioFeedbackResponse(ScenarioFeedbackBase):
    feedback_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True


# 시나리오 시작 요청
class ScenarioStartRequest(BaseModel):
    user_role_id: int
    ai_role_id: int
    description: Optional[str] = None


# 대화 턴 저장 요청
class ConversationTurnRequest(BaseModel):
    user_message: str
    ai_response: str
    turn_number: int


# 시나리오 완료 요청
class ScenarioCompleteRequest(BaseModel):
    final_conversation: List[Dict[str, Any]]
    completion_notes: Optional[str] = None
