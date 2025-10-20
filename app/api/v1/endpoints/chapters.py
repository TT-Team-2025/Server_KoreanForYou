"""
챕터 관련 API 엔드포인트
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional, List

from app.core.database import get_db
from app.core.security import get_current_user_id, oauth2_scheme
from app.schemas.learning import (
    ChapterResponse, ChapterCreate, ChapterUpdate, 
    ChapterListResponse, SentenceListResponse
)
from app.schemas.common import BaseResponse
from app.services.chapter_service import ChapterService

router = APIRouter()


@router.get("/", response_model=ChapterListResponse)
async def get_chapters(
    job_id: Optional[int] = Query(None, description="직무 ID"),
    level_id: Optional[int] = Query(None, description="레벨 ID"),
    page: int = Query(1, ge=1, description="페이지 번호"),
    size: int = Query(20, ge=1, le=100, description="페이지 크기"),
    db: Session = Depends(get_db)
):
    """직무·레벨 기반 챕터 목록 조회"""
    chapter_service = ChapterService(db)
    chapters, total = chapter_service.get_chapters(
        job_id=job_id,
        level_id=level_id,
        page=page,
        size=size
    )
    
    return ChapterListResponse(
        chapters=chapters,
        total=total,
        page=page,
        size=size
    )


@router.get("/{chapter_id}", response_model=ChapterResponse)
async def get_chapter(
    chapter_id: int,
    db: Session = Depends(get_db)
):
    """단일 챕터 상세 조회"""
    chapter_service = ChapterService(db)
    chapter = chapter_service.get_chapter_by_id(chapter_id)
    
    if not chapter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="챕터를 찾을 수 없습니다"
        )
    
    return chapter


@router.post("/", response_model=BaseResponse)
async def create_chapter(
    chapter_data: ChapterCreate,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """새 챕터 생성 (관리자용)"""
    # TODO: 관리자 권한 확인 로직 추가
    chapter_service = ChapterService(db)
    chapter = chapter_service.create_chapter(chapter_data)
    
    return BaseResponse(
        success=True,
        message="챕터가 생성되었습니다",
        data={"chapter_id": chapter.chapter_id}
    )


@router.put("/{chapter_id}", response_model=BaseResponse)
async def update_chapter(
    chapter_id: int,
    chapter_update: ChapterUpdate,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """챕터 수정 (관리자용)"""
    # TODO: 관리자 권한 확인 로직 추가
    chapter_service = ChapterService(db)
    
    if not chapter_service.get_chapter_by_id(chapter_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="챕터를 찾을 수 없습니다"
        )
    
    chapter_service.update_chapter(chapter_id, chapter_update)
    
    return BaseResponse(
        success=True,
        message="챕터가 수정되었습니다"
    )


@router.delete("/{chapter_id}", response_model=BaseResponse)
async def delete_chapter(
    chapter_id: int,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """챕터 삭제 (관리자용)"""
    # TODO: 관리자 권한 확인 로직 추가
    chapter_service = ChapterService(db)
    
    if not chapter_service.get_chapter_by_id(chapter_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="챕터를 찾을 수 없습니다"
        )
    
    chapter_service.delete_chapter(chapter_id)
    
    return BaseResponse(
        success=True,
        message="챕터가 삭제되었습니다"
    )


@router.get("/{chapter_id}/sentences", response_model=SentenceListResponse)
async def get_chapter_sentences(
    chapter_id: int,
    page: int = Query(1, ge=1, description="페이지 번호"),
    size: int = Query(20, ge=1, le=100, description="페이지 크기"),
    db: Session = Depends(get_db)
):
    """챕터 내 문장 목록 조회"""
    chapter_service = ChapterService(db)
    
    if not chapter_service.get_chapter_by_id(chapter_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="챕터를 찾을 수 없습니다"
        )
    
    sentences, total = chapter_service.get_chapter_sentences(
        chapter_id=chapter_id,
        page=page,
        size=size
    )
    
    return SentenceListResponse(
        sentences=sentences,
        total=total,
        page=page,
        size=size
    )
