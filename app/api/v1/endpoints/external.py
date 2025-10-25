"""
외부 API 서비스 관련 엔드포인트 (TTS/STT/LLM)
"""
import os
import asyncio
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any

from app.core.database import get_db
from app.core.security import oauth2_scheme
from app.schemas.common import BaseResponse
from app.services.external_service import ExternalService


router = APIRouter()


@router.post("/stt/file") ## file 형식의 음성파일을 인자로 받아 stt 작업 수행하고 결과를 반환하는 함수 #####
async def transcribe_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    파일 업로드 STT (일반 STT)
    
    음성 파일을 업로드하여 텍스트로 변환합니다.
    
    지원 형식: mp4, m4a, mp3, amr, flac, wav
    """
    # 파일 타입 검증
    allowed_extensions = [".mp4", ".m4a", ".mp3", ".amr", ".flac", ".wav"]
    file_extension = os.path.splitext(file.filename)[1].lower()
    
    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"지원하지 않는 파일 형식입니다. 지원 형식: {', '.join(allowed_extensions)}"
        )
    
    external_service = ExternalService(db)
    
    try:
        # STT 처리 (설정 옵션은 기본값 사용) -> 여기서 설정가능
        config = {
            "model_name": "sommers",
            "language": "ko",
            "use_itn": True,  # 영어/숫자/단위 변환
            "use_disfluency_filter": True,  # 간투어 필터
            "use_profanity_filter": False,  # 비속어 필터
            "use_paragraph_splitter": True,  # 문단 나누기
            "use_word_timestamp": True,
        }
        
        result = await external_service.transcribe_file(file, config)
        
        # transcribe_id 추출
        transcribe_id = result.get("id")
        
        if not transcribe_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="전사 ID를 받지 못했습니다."
            )
        
        # 결과 조회 및 대기
        import asyncio
        final_result = await asyncio.to_thread(
            external_service.rtzr_client.wait_for_result,
            transcribe_id,
            poll_interval_sec=5,
            timeout_sec=3600
        )
        
        status_value = final_result.get("status")
        
        if status_value == "completed":
            return BaseResponse(
                success=True,
                message="전사가 완료되었습니다.",
                data={
                    "transcribe_id": transcribe_id,
                    "results": final_result.get("results", [])
                }
            )
        elif status_value == "failed":
            error_message = final_result.get("message", "전사 실패")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"전사 실패: {error_message}"
            )
        else:
            return BaseResponse(
                success=True,
                message="전사가 진행 중입니다.",
                data={
                    "transcribe_id": transcribe_id,
                    "status": status_value
                }
            )
            
    except TimeoutError as e:
        raise HTTPException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            detail="전사 결과 대기 시간이 초과되었습니다."
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"STT 처리 중 오류: {str(e)}"
        )


@router.get("/stt/file/{transcribe_id}")
async def get_transcribe_result(
    transcribe_id: str,
    db: Session = Depends(get_db)
):
    """
    전사 결과 조회
    
    전사 ID를 사용하여 전사 결과를 조회합니다.
    """
    external_service = ExternalService(db)
    
    try:
        result = await asyncio.to_thread(
            external_service.rtzr_client.get_transcription,
            transcribe_id
        )
        
        return BaseResponse(
            success=True,
            message="전사 결과를 조회했습니다.",
            data=result
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"전사 결과 조회 중 오류: {str(e)}"
        )
