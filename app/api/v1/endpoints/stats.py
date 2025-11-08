"""
통계 관련 API 엔드포인트
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.common import BaseResponse
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

    return BaseResponse(
        success=True,
        message="시나리오 목록을 조회했습니다",
        data=scenario_list
    )

