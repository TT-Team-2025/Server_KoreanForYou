"""
학습 진행 관련 API 엔드포인트
"""
import os

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id, oauth2_scheme
from app.schemas.progress import (
    ProgressStatsResponse, ChapterProgressResponse, UserProgressHistoryResponse,
    UserProgressResponse, SentenceProgressResponse, UserProgressUpdate
)
from app.schemas.common import BaseResponse
from app.services.progress_service import ProgressService

router = APIRouter()


@router.get("/users/{user_id}", response_model=ProgressStatsResponse)
async def get_user_progress(
    user_id: int,
    db: AsyncSession = Depends(get_db)
):
    """사용자의 전체 학습 진행 현황 조회"""
    progress_service = ProgressService(db)
    progress_stats = await progress_service.get_user_progress_stats(user_id)

    if not progress_stats:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="사용자 진행 현황을 찾을 수 없습니다"
        )

    return progress_stats


@router.get("/chapters/{chapter_id}", response_model=ChapterProgressResponse)
async def get_chapter_progress(
    chapter_id: int,
    db: AsyncSession = Depends(get_db)
):
    """특정 챕터의 학습 진행률 조회"""
    progress_service = ProgressService(db)
    chapter_progress = await progress_service.get_chapter_progress(chapter_id)

    if not chapter_progress:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="챕터 진행률을 찾을 수 없습니다"
        )

    return chapter_progress




@router.get("/sentences/{sentence_id}", response_model=SentenceProgressResponse)
async def get_sentence_progress(
    sentence_id: int,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """문장별 진행 상태 조회"""
    user_id = get_current_user_id(token)
    progress_service = ProgressService(db)

    sentence_progress = await progress_service.get_sentence_progress(user_id, sentence_id)

    if not sentence_progress:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="문장 진행 상태를 찾을 수 없습니다"
        )

    return sentence_progress


@router.patch("/sentences/{sentence_id}", response_model=BaseResponse)
async def update_sentence_progress(
    sentence_id: int,
    file: UploadFile = File(..., description="사용자 음성 녹음 파일"),
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """문장 학습 진행(STT 기반) 업데이트"""
    allowed_extensions = [".mp4", ".m4a", ".mp3", ".amr", ".flac", ".wav"]
    file_extension = os.path.splitext(file.filename)[1].lower()

    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"지원하지 않는 파일 형식입니다. 지원 형식: {', '.join(allowed_extensions)}"
        )

    user_id = get_current_user_id(token)
    progress_service = ProgressService(db)

    try:
        progress, mismatch_info = await progress_service.update_sentence_progress(user_id, sentence_id, file)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc)
        ) from exc
    except TimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            detail="전사 결과 대기 시간이 초과되었습니다."
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc)
        ) from exc

    return BaseResponse(
        success=True,
        message="문장 진행 상태가 업데이트되었습니다",
        data={
            "progress_id": progress.progress_id,
            "stt_transcript": progress.stt_transcript,
            "word_timestamps": progress.word_timestamps,
            "total_word_count": progress.total_word_count,
            "recognized_word_count": progress.recognized_word_count,
            "correct_word_count": progress.correct_word_count,
            "start_time": progress.start_time,
            "end_time": progress.end_time,
            "total_time": progress.total_time,
            "missing_words": mismatch_info["missing_words"],
            "extra_words": mismatch_info["extra_words"],
            "utterances": mismatch_info["raw_utterances"]
        }
    )


@router.get("/users/{user_id}/history", response_model=UserProgressHistoryResponse)
async def get_user_progress_history(
    user_id: int,
    db: AsyncSession = Depends(get_db)
):
    """사용자 전체 학습 이력 조회"""
    progress_service = ProgressService(db)
    progress_history = await progress_service.get_user_progress_history(user_id)

    if not progress_history:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="사용자 학습 이력을 찾을 수 없습니다"
        )

    return progress_history
