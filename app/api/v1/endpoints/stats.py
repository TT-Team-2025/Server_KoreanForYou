"""
통계 관련 API 엔드포인트
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id, oauth2_scheme
from app.schemas.common import BaseResponse
from app.schemas.stats import (
    LearningSummaryResponse,
    RecentScenarioItem,
    ChapterFeedbackBrief,
)
from app.services.stats_service import StatsService

router = APIRouter()


@router.get("/scenarios/recent", response_model=BaseResponse)
async def get_recent_scenarios(
    limit: int = 10,
    db: AsyncSession = Depends(get_db)
):
    """최신 시나리오 목록 조회"""
    stats_service = StatsService(db)
    scenario_list = await stats_service.get_recent_scenarios(limit)

    if not scenario_list:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="시나리오를 찾을 수 없습니다"
        )

    items = [RecentScenarioItem(**item) for item in scenario_list]

    return BaseResponse(
        success=True,
        message="시나리오 목록을 조회했습니다",
        data=[item.model_dump() for item in items],
    )


@router.get("/learning/summary", response_model=LearningSummaryResponse)
async def get_learning_summary(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """현재 사용자 학습 요약 정보 조회"""
    user_id = get_current_user_id(token)
    stats_service = StatsService(db)
    return await stats_service.get_learning_summary(user_id)


@router.get("/chapters/recent", response_model=BaseResponse)
async def get_recent_chapter_feedbacks(
    limit: int = 10,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    """최근 완료한 챕터 피드백 목록 조회"""
    user_id = get_current_user_id(token)
    stats_service = StatsService(db)
    feedbacks = await stats_service.get_recent_chapter_feedbacks(user_id, limit)

    items = [ChapterFeedbackBrief(**fb) for fb in feedbacks]

    return BaseResponse(
        success=True,
        message="최근 챕터 피드백을 조회했습니다",
        data=[item.model_dump() for item in items],
    )

