from __future__ import annotations

"""
시나리오 관련 스키마 (DTO)
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


# AI 말하기 연습실 관련 스키마
class StartScenarioRequest(BaseModel):
    """시나리오 세션 시작 요청"""
    topic: str = Field(..., description="대화 주제 (예: 편의점에서 계산하기)")
    my_role: str = Field(..., description="나의 역할")
    ai_role: str = Field(..., description="AI의 역할")
    description: Optional[str] = Field(None, description="상황 설명 (선택)")


class StartScenarioResponse(BaseModel):
    """시나리오 세션 시작 응답"""
    session_id: str
    assistant: str
    assistant_id: str
    tts_filename: Optional[str] = Field(None, description="AI 응답 TTS 오디오 파일명")
    tts_url: Optional[str] = Field(None, description="AI 응답 TTS 오디오 파일 URL")


class SendMessageRequest(BaseModel):
    """텍스트 메시지 전송 요청"""
    thread_id: str = Field(..., description="OpenAI Thread ID")
    message: str


class SendMessageResponse(BaseModel):
    """메시지 전송 응답"""
    assistant: str


class SendVoiceMessageResponse(BaseModel):
    """음성 메시지 전송 응답 (STT + LLM + TTS)"""
    assistant: str
    user_text: str
    tts_filename: Optional[str] = Field(None, description="AI 응답 TTS 오디오 파일명")
    tts_url: Optional[str] = Field(None, description="AI 응답 TTS 오디오 파일 URL")
    pronunciation_score: Optional[float] = Field(None, description="발음 정확도 점수 (0-100)")
    fluency_score: Optional[float] = Field(None, description="유창성 점수 (0-100)")
    grammar_score: Optional[float] = Field(None, description="문법 정확성 점수 (0-100)")
    overall_score: Optional[float] = Field(None, description="종합 점수 (0-100)")
    evaluation_details: Optional[Dict[str, Any]] = Field(
        None,
        description="세부 평가 정보 (발음/유창성/문법 분석 결과)",
    )


class EndScenarioRequest(BaseModel):
    """시나리오 종료 요청"""
    thread_id: str = Field(..., description="OpenAI Thread ID")


class EndScenarioResponse(BaseModel):
    """시나리오 종료 응답"""
    thread_id: str
    completion_status: str
    end_time: Optional[str] = None
    turn_count: int
    total_time: Optional[int] = None
    feedback: Optional["ScenarioFeedbackResponse"] = None


class CompletedScenarioItem(BaseModel):
    """완료된 시나리오 항목 조회 """
    thread_id: str
    scenario_title: str
    scenario_description: Optional[str] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    turn_count: Optional[int] = None
    completion_status: str
    total_time: Optional[int] = None
    
    class Config:
        from_attributes = True


class CompletedScenarioListResponse(BaseModel):
    """완료된 시나리오 목록 응답"""
    scenarios: List[CompletedScenarioItem]
    total: int

# 시나리오 피드백 관련 스키마
class ScenarioFeedbackResponse(BaseModel):
    feedback_id: int
    user_id: Optional[int] = None
    log_id: int
    pronunciation_score: Optional[int] = None
    accuracy_score: Optional[int] = None
    fluency_score: Optional[int] = None
    total_score: Optional[int] = None
    comment: Optional[str] = None
    detail_comment: Optional[Any] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class ConversationMessage(BaseModel):
    """대화 메시지 항목"""
    role: str
    content: str
    created_at: Optional[str] = None

class ConversationResponse(BaseModel):
    """대화 내역 조회 응답"""
    thread_id: str
    scenario_title: Optional[str] = None
    messages: List[ConversationMessage] = []
    total_messages: int = 0


class UserTurnCountResponse(BaseModel):
    """사용자 발화 횟수 조회 응답"""
    user_id: int
    total_turn_count: int
    scenario_count: int  # 시나리오 개수


EndScenarioResponse.model_rebuild(_types_namespace=globals())


class ScenarioSessionSummaryResponse(BaseModel):
    """시나리오 단일 세션 요약 응답"""
    progress_id: int
    thread_id: Optional[str] = None
    scenario_title: Optional[str] = None
    completion_status: Optional[str] = None
    turn_count: Optional[int] = None
    total_time: Optional[int] = None
    total_score: Optional[int] = None
    pronunciation_score: Optional[int] = None
    fluency_score: Optional[int] = None
    grammar_score: Optional[int] = None
    ai_comment: Optional[str] = None
    detail_comment: Optional[Any] = None
    created_at: Optional[datetime] = None

