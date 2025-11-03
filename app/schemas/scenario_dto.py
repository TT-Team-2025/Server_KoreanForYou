"""
시나리오 관련 스키마 (DTO)
"""
from pydantic import BaseModel, Field
from typing import Optional, List
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

# 시나리오 피드백 관련 스키마
class ScenarioFeedbackResponse(BaseModel):
    """시나리오 피드백 응답"""
    feedback_id: int
    user_id: Optional[int] = None
    log_id: int
    pronunciation_score: Optional[int] = None
    accuracy_score: Optional[int] = None
    fluency_score: Optional[int] = None
    completeness_score: Optional[int] = None
    total_score: Optional[int] = None
    comment: Optional[str] = None
    detail_comment: Optional[List[str]] = None
    created_at: datetime
    
    class Config:
        from_attributes = True
