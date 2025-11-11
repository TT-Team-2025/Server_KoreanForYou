"""
피드백 관련 API 엔드포인트
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id, oauth2_scheme
from app.schemas.learning import (
    ChapterFeedbackResponse, ChapterFeedbackCreate,
    SentenceFeedbackResponse, SentenceFeedbackCreate
)
from app.schemas.scenario_dto import ScenarioFeedbackResponse
from app.schemas.common import BaseResponse
from app.services.feedback_service import FeedbackService

router = APIRouter()


# 피드백 저장 -> 피드백 생성 로직으로 구현 필요!
# 매개변수, 내부 로직, db 연동, 서비스 로직 수정 필요

@router.get("/chapters/{chapter_id}", response_model=ChapterFeedbackResponse)
async def get_chapter_feedback(
    chapter_id: int,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """챕터 피드백 조회"""
    user_id = get_current_user_id(token)
    feedback_service = FeedbackService(db)

    feedback = await feedback_service.get_chapter_feedback(user_id, chapter_id)

    if not feedback:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="챕터 피드백을 찾을 수 없습니다"
        )

    return feedback

## 챕터 피드백 생성 구현 필요
@router.post("/chapters/{chapter_id}", response_model=ChapterFeedbackResponse)
async def generate_chapter_feedback(
    chapter_id: int,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """챕터 피드백 생성"""
    user_id = get_current_user_id(token)
    feedback_service = FeedbackService(db)

    feedback = await feedback_service.generate_chapter_feedback(user_id, chapter_id)

    if not feedback:
        raise HTTPException(
            status_code=status.HTTP_404_BAD_REQUEST,
            detail="챕터 피드백 생성에 실패했습니다"
        )

    return feedback


@router.get("/sentences/{sentence_id}", response_model=SentenceFeedbackResponse)
async def get_sentence_feedback(
    sentence_id: int,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """문장 피드백 조회"""
    user_id = get_current_user_id(token)
    feedback_service = FeedbackService(db)

    feedback = await feedback_service.get_sentence_feedback(user_id, sentence_id)

    if not feedback:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="문장 피드백을 찾을 수 없습니다"
        )

    return feedback

## 저장 -> 생성 로직 필요
@router.post("/sentences/{sentence_id}", response_model=SentenceFeedbackResponse)
async def generate_sentence_feedback(
    sentence_id: int,
    feedback_data: SentenceFeedbackCreate,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """문장 피드백 생성"""
    user_id = get_current_user_id(token)
    feedback_service = FeedbackService(db)

    try:
        feedback = await feedback_service.generate_sentence_feedback(user_id, sentence_id, feedback_data)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"문장 피드백 생성에 실패했습니다: {str(e)}"
        )

    return feedback


@router.get("/scenarios/{scenario_id}", response_model=ScenarioFeedbackResponse)
async def get_scenario_feedback(
    scenario_id: int,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """시나리오 피드백 조회"""
    user_id = get_current_user_id(token)
    feedback_service = FeedbackService(db)

    feedback = await feedback_service.get_scenario_feedback(user_id, scenario_id)

    if not feedback:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="시나리오 피드백을 찾을 수 없습니다"
        )

    return feedback
