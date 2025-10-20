"""
외부 API 서비스 관련 엔드포인트 (TTS/STT/LLM)
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.core.security import oauth2_scheme
from app.schemas.common import BaseResponse
from app.services.external_service import ExternalService

router = APIRouter()


@router.post("/tts", response_model=BaseResponse)
async def convert_text_to_speech(
    text: str,
    language: str = "ko",
    voice: str = "default",
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """문장을 음성(TTS)으로 변환"""
    external_service = ExternalService(db)
    
    try:
        tts_result = await external_service.convert_text_to_speech(
            text=text,
            language=language,
            voice=voice
        )
        
        return BaseResponse(
            success=True,
            message="TTS 변환이 완료되었습니다",
            data=tts_result
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"TTS 변환 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/tts/{tts_id}", response_model=BaseResponse)
async def get_tts_result(
    tts_id: str,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """TTS 변환 결과 조회"""
    external_service = ExternalService(db)
    
    tts_result = external_service.get_tts_result(tts_id)
    
    if not tts_result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="TTS 결과를 찾을 수 없습니다"
        )
    
    return BaseResponse(
        success=True,
        message="TTS 결과를 조회했습니다",
        data=tts_result
    )


@router.post("/stt", response_model=BaseResponse)
async def convert_speech_to_text(
    audio_file: UploadFile = File(...),
    language: str = "ko",
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """음성을 텍스트(STT)로 변환"""
    external_service = ExternalService(db)
    
    try:
        stt_result = await external_service.convert_speech_to_text(
            audio_file=audio_file,
            language=language
        )
        
        return BaseResponse(
            success=True,
            message="STT 변환이 완료되었습니다",
            data=stt_result
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"STT 변환 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/stt/{stt_id}", response_model=BaseResponse)
async def get_stt_result(
    stt_id: str,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """STT 변환 결과 조회"""
    external_service = ExternalService(db)
    
    stt_result = external_service.get_stt_result(stt_id)
    
    if not stt_result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="STT 결과를 찾을 수 없습니다"
        )
    
    return BaseResponse(
        success=True,
        message="STT 결과를 조회했습니다",
        data=stt_result
    )


@router.post("/llm/feedback/sentence", response_model=BaseResponse)
async def generate_sentence_feedback(
    sentence_id: int,
    user_audio_url: Optional[str] = None,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """문장 단위 LLM 피드백 요청"""
    external_service = ExternalService(db)
    
    try:
        feedback = await external_service.generate_sentence_feedback(
            sentence_id=sentence_id,
            user_audio_url=user_audio_url
        )
        
        return BaseResponse(
            success=True,
            message="문장 피드백이 생성되었습니다",
            data=feedback
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"피드백 생성 중 오류가 발생했습니다: {str(e)}"
        )


@router.post("/llm/feedback/chapter", response_model=BaseResponse)
async def generate_chapter_feedback(
    chapter_id: int,
    user_progress_data: dict,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """챕터 단위 LLM 피드백 요청"""
    external_service = ExternalService(db)
    
    try:
        feedback = await external_service.generate_chapter_feedback(
            chapter_id=chapter_id,
            user_progress_data=user_progress_data
        )
        
        return BaseResponse(
            success=True,
            message="챕터 피드백이 생성되었습니다",
            data=feedback
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"피드백 생성 중 오류가 발생했습니다: {str(e)}"
        )


@router.post("/llm/feedback/scenario", response_model=BaseResponse)
async def generate_scenario_feedback(
    scenario_id: int,
    conversation_data: dict,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """시나리오 단위 LLM 피드백 요청"""
    external_service = ExternalService(db)
    
    try:
        feedback = await external_service.generate_scenario_feedback(
            scenario_id=scenario_id,
            conversation_data=conversation_data
        )
        
        return BaseResponse(
            success=True,
            message="시나리오 피드백이 생성되었습니다",
            data=feedback
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"피드백 생성 중 오류가 발생했습니다: {str(e)}"
        )
