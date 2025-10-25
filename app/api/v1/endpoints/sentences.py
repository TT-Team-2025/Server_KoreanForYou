"""
문장 관련 API 엔드포인트
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.core.security import oauth2_scheme
from app.schemas.learning import (
    SentenceResponse, SentenceCreate, SentenceUpdate,
    SimilarSentenceResponse
)
from app.schemas.common import BaseResponse
from app.services.sentence_service import SentenceService

router = APIRouter()


@router.get("/{sentence_id}", response_model=SentenceResponse)
async def get_sentence(
    sentence_id: int,
    db: Session = Depends(get_db)
):
    """단일 문장 조회"""
    sentence_service = SentenceService(db)
    sentence = sentence_service.get_sentence_by_id(sentence_id)
    
    if not sentence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="문장을 찾을 수 없습니다"
        )
    
    return sentence


@router.put("/{sentence_id}", response_model=BaseResponse)
async def update_sentence(
    sentence_id: int,
    sentence_update: SentenceUpdate,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """문장 수정 (관리자용)"""
    # TODO: 관리자 권한 확인 로직 추가
    sentence_service = SentenceService(db)
    
    if not sentence_service.get_sentence_by_id(sentence_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="문장을 찾을 수 없습니다"
        )
    
    sentence_service.update_sentence(sentence_id, sentence_update)
    
    return BaseResponse(
        success=True,
        message="문장이 수정되었습니다"
    )


@router.delete("/{sentence_id}", response_model=BaseResponse)
async def delete_sentence(
    sentence_id: int,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """문장 삭제 (관리자용)"""
    # TODO: 관리자 권한 확인 로직 추가
    sentence_service = SentenceService(db)
    
    if not sentence_service.get_sentence_by_id(sentence_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="문장을 찾을 수 없습니다"
        )
    
    sentence_service.delete_sentence(sentence_id)
    
    return BaseResponse(
        success=True,
        message="문장이 삭제되었습니다"
    )


@router.get("/{sentence_id}/similar", response_model=List[SimilarSentenceResponse])
async def get_similar_sentences(
    sentence_id: int,
    db: Session = Depends(get_db)
):
    """해당 문장의 유사 문장 목록 조회"""
    sentence_service = SentenceService(db)
    
    if not sentence_service.get_sentence_by_id(sentence_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="문장을 찾을 수 없습니다"
        )
    
    similar_sentences = sentence_service.get_similar_sentences(sentence_id)
    return similar_sentences
