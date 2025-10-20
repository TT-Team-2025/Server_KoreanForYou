"""
피드백 관련 API 엔드포인트
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user_id, oauth2_scheme
from app.schemas.learning import (
    ChapterFeedbackResponse, ChapterFeedbackCreate,
    SentenceFeedbackResponse, SentenceFeedbackCreate
)
from app.schemas.scenario import ScenarioFeedbackResponse
from app.schemas.common import BaseResponse
from app.services.feedback_service import FeedbackService

router = APIRouter()


@router.get("/chapters/{chapter_id}", response_model=ChapterFeedbackResponse)
async def get_chapter_feedback(
    chapter_id: int,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """챕터 피드백 조회"""
    user_id = get_current_user_id(token)
    feedback_service = FeedbackService(db)
    
    feedback = feedback_service.get_chapter_feedback(user_id, chapter_id)
    
    if not feedback:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="챕터 피드백을 찾을 수 없습니다"
        )
    
    return feedback


@router.post("/chapters/{chapter_id}", response_model=BaseResponse)
async def save_chapter_feedback(
    chapter_id: int,
    feedback_data: ChapterFeedbackCreate,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """챕터 피드백 저장"""
    user_id = get_current_user_id(token)
    feedback_service = FeedbackService(db)
    
    feedback_service.save_chapter_feedback(user_id, chapter_id, feedback_data)
    
    return BaseResponse(
        success=True,
        message="챕터 피드백이 저장되었습니다"
    )


@router.get("/sentences/{sentence_id}", response_model=SentenceFeedbackResponse)
async def get_sentence_feedback(
    sentence_id: int,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """문장 피드백 조회"""
    user_id = get_current_user_id(token)
    feedback_service = FeedbackService(db)
    
    feedback = feedback_service.get_sentence_feedback(user_id, sentence_id)
    
    if not feedback:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="문장 피드백을 찾을 수 없습니다"
        )
    
    return feedback


@router.post("/sentences/{sentence_id}", response_model=BaseResponse)
async def save_sentence_feedback(
    sentence_id: int,
    feedback_data: SentenceFeedbackCreate,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """문장 피드백 저장"""
    user_id = get_current_user_id(token)
    feedback_service = FeedbackService(db)
    
    feedback_service.save_sentence_feedback(user_id, sentence_id, feedback_data)
    
    return BaseResponse(
        success=True,
        message="문장 피드백이 저장되었습니다"
    )


@router.get("/scenarios/{scenario_id}", response_model=ScenarioFeedbackResponse)
async def get_scenario_feedback(
    scenario_id: int,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """시나리오 피드백 조회"""
    user_id = get_current_user_id(token)
    feedback_service = FeedbackService(db)
    
    feedback = feedback_service.get_scenario_feedback(user_id, scenario_id)
    
    if not feedback:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="시나리오 피드백을 찾을 수 없습니다"
        )
    
    return feedback
