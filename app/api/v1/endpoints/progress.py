"""
학습 진행 관련 API 엔드포인트
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user_id, oauth2_scheme
from app.schemas.progress import (
    ProgressStatsResponse, ChapterProgressResponse, UserProgressHistoryResponse,
    UserProgressResponse, SentenceProgressResponse, UserProgressUpdate, SentenceProgressUpdate
)
from app.schemas.common import BaseResponse
from app.services.progress_service import ProgressService

router = APIRouter()


@router.get("/users/{user_id}", response_model=ProgressStatsResponse)
async def get_user_progress(
    user_id: int,
    db: Session = Depends(get_db)
):
    """사용자의 전체 학습 진행 현황 조회"""
    progress_service = ProgressService(db)
    progress_stats = progress_service.get_user_progress_stats(user_id)
    
    if not progress_stats:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="사용자 진행 현황을 찾을 수 없습니다"
        )
    
    return progress_stats


@router.get("/chapters/{chapter_id}", response_model=ChapterProgressResponse)
async def get_chapter_progress(
    chapter_id: int,
    db: Session = Depends(get_db)
):
    """특정 챕터의 학습 진행률 조회"""
    progress_service = ProgressService(db)
    chapter_progress = progress_service.get_chapter_progress(chapter_id)
    
    if not chapter_progress:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="챕터 진행률을 찾을 수 없습니다"
        )
    
    return chapter_progress


@router.post("/chapters/{chapter_id}", response_model=BaseResponse)
async def update_chapter_progress(
    chapter_id: int,
    progress_update: UserProgressUpdate,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """챕터 진행률 저장/갱신"""
    user_id = get_current_user_id(token)
    progress_service = ProgressService(db)
    
    progress_service.update_user_progress(user_id, chapter_id, progress_update)
    
    return BaseResponse(
        success=True,
        message="챕터 진행률이 업데이트되었습니다"
    )


@router.get("/sentences/{sentence_id}", response_model=SentenceProgressResponse)
async def get_sentence_progress(
    sentence_id: int,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """문장별 진행 상태 조회"""
    user_id = get_current_user_id(token)
    progress_service = ProgressService(db)
    
    sentence_progress = progress_service.get_sentence_progress(user_id, sentence_id)
    
    if not sentence_progress:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="문장 진행 상태를 찾을 수 없습니다"
        )
    
    return sentence_progress


@router.patch("/sentences/{sentence_id}", response_model=BaseResponse)
async def update_sentence_progress(
    sentence_id: int,
    progress_update: SentenceProgressUpdate,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """문장 학습 완료 상태 업데이트"""
    user_id = get_current_user_id(token)
    progress_service = ProgressService(db)
    
    progress_service.update_sentence_progress(user_id, sentence_id, progress_update)
    
    return BaseResponse(
        success=True,
        message="문장 진행 상태가 업데이트되었습니다"
    )


@router.get("/users/{user_id}/history", response_model=UserProgressHistoryResponse)
async def get_user_progress_history(
    user_id: int,
    db: Session = Depends(get_db)
):
    """사용자 전체 학습 이력 조회"""
    progress_service = ProgressService(db)
    progress_history = progress_service.get_user_progress_history(user_id)
    
    if not progress_history:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="사용자 학습 이력을 찾을 수 없습니다"
        )
    
    return progress_history
