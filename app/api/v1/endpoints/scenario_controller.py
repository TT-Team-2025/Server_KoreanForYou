"""
시나리오 기반 AI 말하기 연습실 엔드포인트 (Assistants API - Threads)
"""

import os
import uuid
import asyncio
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import oauth2_scheme
from app.services.scenario_service import ScenarioService
from app.services.external_service import ExternalService
from app.services.user_service import UserService
from app.schemas.scenario_dto import (
    StartScenarioRequest,
    StartScenarioResponse,
    SendMessageRequest,
    SendMessageResponse,
    SendVoiceMessageResponse,
    EndScenarioRequest,
    EndScenarioResponse,
)


router = APIRouter()

# TTS 파일 저장 디렉토리
TTS_UPLOAD_DIR = "uploads/tts"
os.makedirs(TTS_UPLOAD_DIR, exist_ok=True)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """현재 사용자 정보 가져오기"""
    from app.core.security import get_current_user_id
    user_id = get_current_user_id(token)
    user_service = UserService(db)
    user = user_service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="사용자를 찾을 수 없습니다"
        )
    return user


@router.post("/start", response_model=StartScenarioResponse) #세션 처음 시작할때 요청 ㄱㄱ
async def start_session(
    req: StartScenarioRequest,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    service = ScenarioService(db)
    try:
        result = await service.start_scenario(
            user_id=current_user.user_id,
            topic=req.topic,
            user_role=req.my_role,
            ai_role=req.ai_role,
            description=req.description,
        )
        return StartScenarioResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"세션 시작 중 오류: {str(e)}",
        )


@router.post("/message", response_model=SendMessageResponse) #메세지 보내는 api text형식
async def send_message(req: SendMessageRequest, db: Session = Depends(get_db)):
    service = ScenarioService(db)
    try:
        result = await service.send_message(thread_id=req.thread_id, user_text=req.message)
        return SendMessageResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except TimeoutError as e:
        raise HTTPException(status_code=status.HTTP_408_REQUEST_TIMEOUT, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"대화 처리 중 오류: {str(e)}",
        )


@router.post("/end", response_model=EndScenarioResponse) #시나리오 종료 api
async def end_scenario(req: EndScenarioRequest, db: Session = Depends(get_db)):
    """시나리오 종료: completion_status를 COMPLETED로 변경하고 end_time 저장"""
    service = ScenarioService(db)
    try:
        result = await service.end_scenario(thread_id=req.thread_id)
        return EndScenarioResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"시나리오 종료 중 오류: {str(e)}",
        )


@router.post("/message/voice", response_model=SendVoiceMessageResponse) # 음성 파일 → STT + LLM 동시 처리
async def send_voice_message(
    thread_id: str = Form(..., description="OpenAI Thread ID"),
    file: UploadFile = File(..., description="음성 파일"),
    request: Request = None,
    db: Session = Depends(get_db)
):
    """
    음성 파일을 업로드하여 STT 변환 후 AI 응답 받기
    
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
    
    scenario_service = ScenarioService(db)
    external_service = ExternalService(db)
    
    try:
        # 1) STT 처리
        config = {
            "model_name": "sommers",
            "language": "ko",
            "use_itn": True,
            "use_disfluency_filter": True,
            "use_profanity_filter": False,
            "use_paragraph_splitter": True,
            "use_word_timestamp": True,
        }
        
        stt_result = await external_service.transcribe_file(file, config)
        print(f"STT 전사 결과: {stt_result}")
        
        transcribe_id = stt_result.get("id")
        
        if not transcribe_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="전사 ID를 받지 못했습니다."
            )
        
        # 2) STT 결과 대기 및 텍스트 추출
        final_result = await asyncio.to_thread(
            external_service.rtzr_client.wait_for_result,
            transcribe_id,
            poll_interval_sec=5,
            timeout_sec=3600
        )
        
        print(f"STT 최종 결과: {final_result}")
        
        if final_result.get("status") != "completed":
            error_message = final_result.get("message", "전사 실패")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"전사 실패: {error_message}"
            )
        
        # 3) STT 결과에서 텍스트 추출 (RTZR은 results.utterances[].msg에 전체 문장을 제공)
        results = final_result.get("results", {})
        utterances = results.get("utterances", []) if isinstance(results, dict) else [] #타임스탬프
        user_text = ""
        
        if utterances and len(utterances) > 0:
            # 첫 번째 utterance의 msg 필드에 전체 문장이 있음
            user_text = utterances[0].get("msg", "")
        
        if not user_text:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="음성에서 텍스트를 추출하지 못했습니다."
            )
        
        # 4) 변환된 텍스트로 AI 응답 받기
        result = await scenario_service.send_message(thread_id=thread_id, user_text=user_text)
        assistant_text = result["assistant"]
        
        # 5) AI 응답을 TTS로 변환하고 파일로 저장
        tts_filename = None
        try:
            tts_audio = await external_service.text_to_speech(
                text=assistant_text,
                speaker="nara",  # 기본 음성
                speed=0,
                volume=0,
                pitch=0,
                emotion="neutral",
                format="mp3"
            )
            # 고유 파일명 생성
            filename = f"{uuid.uuid4()}.mp3"
            file_path = os.path.join(TTS_UPLOAD_DIR, filename)
            
            # 파일 저장
            with open(file_path, "wb") as f:
                f.write(tts_audio)
            
            tts_filename = filename
        except Exception as e:
            # TTS 실패해도 텍스트 응답은 반환
            print(f"TTS 변환 실패: {str(e)}")
        
        return SendVoiceMessageResponse(
            assistant=assistant_text,
            user_text=user_text,
            tts_filename=tts_filename
        )

        
    except TimeoutError as e:
        raise HTTPException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            detail="전사 결과 대기 시간이 초과되었습니다."
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"음성 메시지 처리 중 오류: {str(e)}",
        )


@router.get("/audio/{filename}", name="get_audio_file")
async def get_audio_file(filename: str):
    """
    TTS 오디오 파일 다운로드
    
    Args:
        filename: 다운로드할 오디오 파일명
    """
    file_path = os.path.join(TTS_UPLOAD_DIR, filename)
    
    # 파일 존재 확인
    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="파일을 찾을 수 없습니다."
        )
    
    # 파일 확장자 검증 (보안)
    if not filename.endswith('.mp3'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="지원하지 않는 파일 형식입니다."
        )
    
    return FileResponse(
        path=file_path,
        media_type="audio/mpeg",
        filename=filename
    )


