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
    from app.services.progress_service import ProgressService
    
    user_id = get_current_user_id(token)
    feedback_service = FeedbackService(db)

    feedback = await feedback_service.get_sentence_feedback(user_id, sentence_id)

    if not feedback:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="문장 피드백을 찾을 수 없습니다"
        )

    # sentence_progress에서 word_timestamps와 점수 정보 가져오기
    sentence_progress = feedback.sentence_progress
    word_timestamps = sentence_progress.word_timestamps if sentence_progress else None
    
    # 점수 계산 (sentence_progress에 저장된 정보 기반)
    pronunciation_score = None
    accuracy_score = None
    overall_score = None
    
    if sentence_progress:
        # word_timestamps 기반 발음 점수 계산
        if word_timestamps and isinstance(word_timestamps, list) and len(word_timestamps) > 0:
            if isinstance(word_timestamps[0], dict):
                progress_service = ProgressService(db)
                pronunciation_score, _ = progress_service._calculate_pronunciation_metrics(
                    word_timestamps, []
                )
        
        # 정확도 점수 계산
        if sentence_progress.total_word_count and sentence_progress.correct_word_count:
            accuracy_score = int(
                (sentence_progress.correct_word_count / sentence_progress.total_word_count) * 100
            )
        
        # 전체 점수 계산
        if pronunciation_score is not None and accuracy_score is not None:
            overall_score = int((pronunciation_score + accuracy_score) / 2)
        elif pronunciation_score is not None:
            overall_score = int(pronunciation_score)
        elif accuracy_score is not None:
            overall_score = accuracy_score

    # 응답에 추가 정보 포함
    response_data = {
        "feedback_id": feedback.feedback_id,
        "user_id": feedback.user_id,
        "sentence_id": feedback.sentence_id,
        "sentence_progress_id": feedback.sentence_progress_id,
        "weaknesses": feedback.weaknesses,
        "word_timestamps": word_timestamps,
        "pronunciation_score": pronunciation_score,
        "accuracy_score": accuracy_score,
        "overall_score": overall_score,
    }
    
    return SentenceFeedbackResponse(**response_data)

## 저장 -> 생성 로직 필요
@router.post("/sentences/{sentence_id}", response_model=SentenceFeedbackResponse)
async def generate_sentence_feedback(
    feedback_data: SentenceFeedbackCreate,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """문장 피드백 생성"""
    from app.services.progress_service import ProgressService
    
    user_id = get_current_user_id(token)
    feedback_service = FeedbackService(db)

    try:
        feedback = await feedback_service.generate_sentence_feedback(feedback_data)
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

    # sentence_progress에서 word_timestamps와 점수 정보 가져오기
    sentence_progress = feedback.sentence_progress
    word_timestamps = sentence_progress.word_timestamps if sentence_progress else None
    
    # 점수 계산 (sentence_progress에 저장된 정보 기반)
    pronunciation_score = None
    accuracy_score = None
    overall_score = None
    
    if sentence_progress:
        # word_timestamps 기반 발음 점수 계산
        if word_timestamps and isinstance(word_timestamps, list) and len(word_timestamps) > 0:
            if isinstance(word_timestamps[0], dict):
                progress_service = ProgressService(db)
                pronunciation_score, _ = progress_service._calculate_pronunciation_metrics(
                    word_timestamps, []
                )
        
        # 정확도 점수 계산
        if sentence_progress.total_word_count and sentence_progress.correct_word_count:
            accuracy_score = int(
                (sentence_progress.correct_word_count / sentence_progress.total_word_count) * 100
            )
        
        # 전체 점수 계산
        if pronunciation_score is not None and accuracy_score is not None:
            overall_score = int((pronunciation_score + accuracy_score) / 2)
        elif pronunciation_score is not None:
            overall_score = int(pronunciation_score)
        elif accuracy_score is not None:
            overall_score = accuracy_score
            
        if pronunciation_score is not None: pronunciation_score = int(pronunciation_score)
        if accuracy_score is not None: accuracy_score = int(accuracy_score)
        if overall_score is not None: overall_score = int(overall_score)

    # 응답에 추가 정보 포함
    response_data = {
        "feedback_id": feedback.feedback_id,
        "user_id": feedback.user_id,
        "sentence_id": feedback.sentence_id,
        "sentence_progress_id": feedback.sentence_progress_id,
        "weaknesses": feedback.weaknesses,
        "word_timestamps": word_timestamps,
        "pronunciation_score": pronunciation_score,
        "accuracy_score": accuracy_score,
        "overall_score": overall_score,
    }
    
    return SentenceFeedbackResponse(**response_data)


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
