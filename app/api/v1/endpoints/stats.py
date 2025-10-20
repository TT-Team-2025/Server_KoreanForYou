"""
통계 관련 API 엔드포인트
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import oauth2_scheme
from app.schemas.common import BaseResponse
from app.services.stats_service import StatsService

router = APIRouter()


@router.get("/users/{user_id}", response_model=BaseResponse)
async def get_user_stats(
    user_id: int,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """사용자 전체 통계 조회"""
    stats_service = StatsService(db)
    
    user_stats = stats_service.get_user_stats(user_id)
    
    if not user_stats:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="사용자 통계를 찾을 수 없습니다"
        )
    
    return BaseResponse(
        success=True,
        message="사용자 통계를 조회했습니다",
        data=user_stats
    )


@router.get("/chapters/{chapter_id}", response_model=BaseResponse)
async def get_chapter_stats(
    chapter_id: int,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """챕터별 통계 조회"""
    stats_service = StatsService(db)
    
    chapter_stats = stats_service.get_chapter_stats(chapter_id)
    
    if not chapter_stats:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="챕터 통계를 찾을 수 없습니다"
        )
    
    return BaseResponse(
        success=True,
        message="챕터 통계를 조회했습니다",
        data=chapter_stats
    )


@router.get("/scenarios/{scenario_id}", response_model=BaseResponse)
async def get_scenario_stats(
    scenario_id: int,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """시나리오별 통계 조회"""
    stats_service = StatsService(db)
    
    scenario_stats = stats_service.get_scenario_stats(scenario_id)
    
    if not scenario_stats:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="시나리오 통계를 찾을 수 없습니다"
        )
    
    return BaseResponse(
        success=True,
        message="시나리오 통계를 조회했습니다",
        data=scenario_stats
    )


@router.get("/api", response_model=BaseResponse)
async def get_api_usage_stats(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """API 사용량 통계 조회 (TTS/STT/LLM)"""
    stats_service = StatsService(db)
    
    api_stats = stats_service.get_api_usage_stats()
    
    return BaseResponse(
        success=True,
        message="API 사용량 통계를 조회했습니다",
        data=api_stats
    )
