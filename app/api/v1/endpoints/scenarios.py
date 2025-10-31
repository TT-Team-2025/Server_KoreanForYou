"""
시나리오 기반 AI 말하기 연습실 엔드포인트 (Assistants API - Threads)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.scenario_service import ScenarioService


router = APIRouter()


class StartScenarioRequest(BaseModel):
    topic: str = Field(..., description="대화 주제 (예: 편의점에서 계산하기)")
    my_role: str = Field(..., description="나의 역할")
    ai_role: str = Field(..., description="AI의 역할")
    description: str | None = Field(None, description="상황 설명 (선택)")


class StartScenarioResponse(BaseModel):
    session_id: str
    assistant: str
    assistant_id: str


class SendMessageRequest(BaseModel):
    thread_id: str = Field(..., description="OpenAI Thread ID")
    message: str


class SendMessageResponse(BaseModel):
    assistant: str


@router.post("/session/start", response_model=StartScenarioResponse) #세션 처음 시작할때 요청 ㄱㄱ
async def start_session(req: StartScenarioRequest, db: Session = Depends(get_db)):
    service = ScenarioService(db)
    try:
        result = await service.start_scenario(
            topic=req.topic,
            user_role=req.my_role,
            ai_role=req.ai_role,
            description=req.description,
        )
        return StartScenarioResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"세션 시작 중 오류: {str(e)}",
        )


@router.post("/session/message", response_model=SendMessageResponse) #메세지 보내는 api
async def send_message(req: SendMessageRequest, db: Session = Depends(get_db)):
    service = ScenarioService(db)
    try:
        result = await service.send_message(thread_id=req.thread_id, user_text=req.message)
        return SendMessageResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except TimeoutError as e:
        raise HTTPException(status_code=status.HTTP_408_REQUEST_TIMEOUT, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"대화 처리 중 오류: {str(e)}",
        )


