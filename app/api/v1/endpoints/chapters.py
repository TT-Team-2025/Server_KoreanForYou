"""
챕터 관련 API 엔드포인트
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
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

@router.post('/categories', response_model=BaseResponse)
async def generate_categories(
    job_id: int,
    db: AsyncSession = Depends(get_db)
):
    """학습 카테고리 생성 (관리자용)"""
    chapter_service = ChapterService(db)
    categories = await chapter_service.generate_learning_categories(job_id)

    return BaseResponse(
        success=True,
        message="학습 카테고리가 생성되었습니다",
        data=categories
    )

@router.get("/", response_model=ChapterListResponse)
async def get_chapters(
    job_id: Optional[int] = Query(None, description="직무 ID"),
    level_id: Optional[int] = Query(None, description="레벨 ID"),
    page: int = Query(1, ge=1, description="페이지 번호"),
    size: int = Query(20, ge=1, le=100, description="페이지 크기"),
    group: Optional[str] = Query(all, description="완료 여부 필터링"),
    db: AsyncSession = Depends(get_db)
):
    """직무·레벨 기반 챕터 목록 조회"""
    chapter_service = ChapterService(db)
    chapters, total = await chapter_service.get_chapters(
        user_id=get_current_user_id,
        job_id=job_id,
        level_id=level_id,
        page=page,
        size=size,
        group=group
    )

    return ChapterListResponse(
        chapters=chapters,
        total=total,
        page=page,
        size=size,
        group=group
    )


@router.get("/{chapter_id}", response_model=ChapterResponse)
async def get_chapter(
    chapter_id: int,
    db: AsyncSession = Depends(get_db)
):
    """단일 챕터 상세 조회"""
    chapter_service = ChapterService(db)
    chapter = await chapter_service.get_chapter_by_id(chapter_id)

    if not chapter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="챕터를 찾을 수 없습니다"
        )

    return chapter


# 새 챕터 생성은 LLM 서비스 연동 및 스키마 재검토 필요 -> 세부 내용을 조정하는 층(챕터 제목, 레벨 등) 논의 필요
@router.post("/", response_model=BaseResponse)
async def create_chapter(
    chapter_data: ChapterCreate,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """새 챕터 생성 (관리자용)"""
    # TODO: 관리자 권한 확인 로직 추가
    chapter_service = ChapterService(db)
    chapters = await chapter_service.create_chapter(chapter_data)

    return BaseResponse(
        success=True,
        message="챕터가 생성되었습니다",
        data= [ch.chapter_id for ch in chapters]
    )


# 추후 디벨롭 필요
@router.put("/{chapter_id}", response_model=BaseResponse)
async def update_chapter(
    chapter_id: int,
    chapter_update: ChapterUpdate,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """챕터 수정 (관리자용)"""
    # TODO: 관리자 권한 확인 로직 추가
    chapter_service = ChapterService(db)

    if not await chapter_service.get_chapter_by_id(chapter_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="챕터를 찾을 수 없습니다"
        )

    await chapter_service.update_chapter(chapter_id, chapter_update)

    return BaseResponse(
        success=True,
        message="챕터가 수정되었습니다"
    )


# 추후 디벨롭 필요
@router.delete("/{chapter_id}", response_model=BaseResponse)
async def delete_chapter(
    chapter_id: int,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """챕터 삭제 (관리자용)"""
    # TODO: 관리자 권한 확인 로직 추가
    chapter_service = ChapterService(db)

    if not await chapter_service.get_chapter_by_id(chapter_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="챕터를 찾을 수 없습니다"
        )

    await chapter_service.delete_chapter(chapter_id)

    return BaseResponse(
        success=True,
        message="챕터가 삭제되었습니다"
    )


@router.get("/{chapter_id}/sentences", response_model=SentenceListResponse)
async def get_chapter_sentences(
    chapter_id: int,
    page: int = Query(1, ge=1, description="페이지 번호"),
    size: int = Query(20, ge=1, le=100, description="페이지 크기"),
    db: AsyncSession = Depends(get_db)
):
    """챕터 내 문장 목록 조회"""
    chapter_service = ChapterService(db)

    if not await chapter_service.get_chapter_by_id(chapter_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="챕터를 찾을 수 없습니다"
        )

    sentences, total = await chapter_service.get_chapter_sentences(
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
