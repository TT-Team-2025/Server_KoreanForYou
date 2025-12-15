"""
외부 API 서비스 관련 엔드포인트 (TTS/STT/LLM)
"""
import os
import asyncio
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Dict, Any
from pydantic import BaseModel
import io

from app.core.database import get_db
from app.core.security import oauth2_scheme
from app.schemas.common import BaseResponse
from app.services.external_service import ExternalService

router = APIRouter()


class TTSRequest(BaseModel):
    """TTS 요청 스키마"""
    text: str
    speaker: str = "alloy"  # OpenAI 기본 voice
    speed: float = 1.2  # 1.2배속
    volume: int = 6  # 볼륨 증폭 6dB (약 2배)
    pitch: int = 0
    emotion: str = "neutral"
    format: str = "mp3"


class LLMRequest(BaseModel):
    """LLM 요청 스키마"""
    prompt: str
    prompt_role: str = "user"
    model: Optional[str] = None
    temperature: float = 0.7
    max_tokens: Optional[int] = None


@router.post("/tts")
async def text_to_speech(
    request: TTSRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    텍스트를 음성으로 변환 (바이트 데이터 반환)
    
    텍스트를 받아서 CLOVA VOICE API를 통해 음성으로 변환합니다.
    """
    external_service = ExternalService(db)
    
    try:
        audio_data = await external_service.text_to_speech(
            text=request.text,
            speaker=request.speaker,
            speed=request.speed,
            volume=request.volume,
            pitch=request.pitch,
            emotion=request.emotion,
            format=request.format
        )
        
        # 바이트 데이터를 스트리밍 응답으로 반환
        audio_stream = io.BytesIO(audio_data)
        
        return StreamingResponse(
            io.BytesIO(audio_data),
            media_type=f"audio/{request.format}",
            headers={
                "Content-Disposition": f"attachment; filename=tts_output.{request.format}"
            }
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"TTS 처리 중 오류: {str(e)}"
        )


@router.post("/tts/file")
async def text_to_speech_file(
    text: str = Form(...),
    speaker: str = Form("alloy"),
    speed: float = Form(1.2),
    volume: int = Form(6),
    pitch: int = Form(0),
    emotion: str = Form("neutral"),
    format: str = Form("mp3"),
    db: AsyncSession = Depends(get_db)
):
    """
    텍스트를 음성 파일로 변환하여 저장
    
    텍스트를 받아서 CLOVA VOICE API를 통해 음성 파일로 변환하고 서버에 저장합니다.
    """
    external_service = ExternalService(db)
    
    try:
        # 파일명 생성 (타임스탬프 포함)
        import time
        timestamp = int(time.time())
        filename = f"tts_{timestamp}.{format}"
        output_path = os.path.join("uploads", "tts", filename)
        
        file_path = await external_service.text_to_speech_file(
            text=text,
            output_path=output_path,
            speaker=speaker,
            speed=speed,
            volume=volume,
            pitch=pitch,
            emotion=emotion,
            format=format
        )
        
        return BaseResponse(
            success=True,
            message="음성 파일이 생성되었습니다.",
            data={
                "file_path": file_path,
                "filename": filename,
                "text": text,
                "speaker": speaker,
                "format": format
            }
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"TTS 파일 생성 중 오류: {str(e)}"
        )


@router.post("/stt/file") ## file 형식의 음성파일을 인자로 받아 stt 작업 수행하고 결과를 반환하는 함수 #####
async def transcribe_file(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
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
    db: AsyncSession = Depends(get_db)
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


@router.post("/llm/generate")
async def generate_text_with_llm(
    request: LLMRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    LLM을 사용하여 텍스트 생성 (텍스트 입력 -> 텍스트 출력)
    
    프롬프트를 입력받아 LLM API를 통해 텍스트를 생성합니다.
    """
    external_service = ExternalService(db)
    
    try:
        result = await external_service.llm_service.generate_text(
            prompt=request.prompt,
            prompt_role=request.prompt_role,
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )
        
        return BaseResponse(
            success=True,
            message="텍스트 생성이 완료되었습니다.",
            data={
                **result,  # generated_text, model, max_tokens, usage, finish_reason, full_response 포함
                "prompt": request.prompt,
                "prompt_role": request.prompt_role,
                "request_model": request.model,  # 요청에서 보낸 model (None일 수 있음)
                "request_max_tokens": request.max_tokens  # 요청에서 보낸 max_tokens
            }
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"LLM 텍스트 생성 중 오류: {str(e)}"
        )
