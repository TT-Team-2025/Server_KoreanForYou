"""
외부 API 서비스 관련 서비스 (TTS/STT/LLM)
"""

import sys
import os
import argparse
import time
import pyaudio
import queue
import time
import grpc
import logging
import json
import asyncio
import tempfile
from dotenv import load_dotenv

# .env 파일 로드 (최상단에서 한 번만 실행)
load_dotenv()

from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
import boto3
from botocore.exceptions import BotoCoreError, ClientError
import httpx
import uuid
from fastapi import UploadFile

from requests import Session as RequestsSession

from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

from pydub import AudioSegment 
import grpc
#import soundfile as sf
from app.proto import vito_stt_client_pb2 as pb
from app.proto import vito_stt_client_pb2_grpc as pb_grpc

try:
    import pyaudio
except ImportError:
    print("pyaudio가 설치되지 않았습니다. pip install pyaudio를 실행하세요.")
    pyaudio = None

CHUNK = 1024                    # 한 번에 읽을 오디오 데이터 크기 작을수록 실시간성 ↑, 클수록 효율성 ↑
FORMAT = pyaudio.paInt16       # 오디오 데이터 형식 (16비트 정수)
CHANNELS = 1                   # 채널 수 (1=모노, 2=스테레오) 모노 = 한개스피고, 스테레오  = 좌우 스피커
RATE = 8000                    # 샘플링 레이트 (초당 8000개 샘플) 80000HZ = 전화품질 16000 = 일반 음성
SAMPLE_RATE = 8000             # 위와 동일
ENCODING = pb.DecoderConfig.AudioEncoding.LINEAR16 #인코딩 정보

# pyaudio 초기화는 실제 사용 시점에만 수행 (Docker 환경에서는 마이크가 없으므로)
_pyaudio_instance = None
_stream_instance = None

API_BASE = "https://openapi.vito.ai"
GRPC_SERVER_URL = "grpc-openapi.vito.ai:443"

# 환경 변수 읽기 (os.environ에서 가져오기)
CLIENT_ID = os.environ.get("RETURN_ZERO_CLIENT_ID")
CLIENT_SECRET = os.environ.get("RETURN_ZERO_CLIENT_SECRET")
CLOVA_VOICE_CLIENT_ID = os.environ.get("CLOVA_VOICE_CLIENT_ID")
CLOVA_VOICE_CLIENT_SECRET = os.environ.get("CLOVA_VOICE_CLIENT_SECRET")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")

# 로거 설정
logger = logging.getLogger(__name__)

logger.debug("환경 변수 로드 시도")
# 환경 변수가 설정되지 않은 경우 경고 출력 및 기본값 설정
if not CLIENT_ID or not CLIENT_SECRET:
    logger.warning("RETURN_ZERO_CLIENT_ID and RETURN_ZERO_CLIENT_SECRET not set. STT기능을 사용할 수 없습니다.")
if not CLOVA_VOICE_CLIENT_ID or not CLOVA_VOICE_CLIENT_SECRET:
    logger.warning("CLOVA_VOICE_CLIENT_ID and CLOVA_VOICE_CLIENT_SECRET not set. TTS 기능을 사용할 수 없습니다.")

class ExternalService:
    def __init__(self, db: Session):
        self.db = db
        self.rtzr_client = RTZROpenAPIClient(
           CLIENT_ID ,
            CLIENT_SECRET
        )
        # OpenAI TTS 사용 (Clova Voice 대신)
        self.tts_client = OpenAITTSClient(OPENAI_API_KEY)
        self.llm_service = LLMService(db)
        self.s3_bucket = os.environ.get("S3_BUCKET_NAME")
        self.s3_region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
        self.s3_presign_expiration = int(os.environ.get("S3_PRESIGNED_EXPIRATION", "3600"))
        self.s3_client = None
        if self.s3_bucket:
            try:
                self.s3_client = boto3.client(
                    "s3",
                    region_name=self.s3_region,
                    aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
                    aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
                )
            except Exception as exc:
                logger.warning("S3 클라이언트 초기화 실패: %s", exc)
                self.s3_client = None

    @property
    def s3_available(self) -> bool:
        return self.s3_client is not None and bool(self.s3_bucket)

    def _build_s3_key(self, prefix: str, extension: str) -> str:
        safe_prefix = prefix.strip("/ ")
        return f"{safe_prefix}/{uuid.uuid4().hex}{extension}"

    async def _upload_bytes_to_s3(
        self,
        data: bytes,
        *,
        prefix: str,
        extension: str,
        content_type: str,
    ) -> Optional[str]:
        if not self.s3_available:
            return None

        key = self._build_s3_key(prefix, extension)

        def _upload():
            self.s3_client.put_object(
                Bucket=self.s3_bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
            )

        try:
            await asyncio.to_thread(_upload)
            return key
        except (BotoCoreError, ClientError, ValueError) as exc:
            logger.error("S3 업로드 실패: %s", exc)
            return None

    async def generate_presigned_url(
        self,
        key: str,
        expires_in: Optional[int] = None,
    ) -> Optional[str]:
        if not self.s3_available:
            return None

        expiration = expires_in or self.s3_presign_expiration

        def _generate():
            return self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.s3_bucket, "Key": key},
                ExpiresIn=expiration,
            )

        try:
            return await asyncio.to_thread(_generate)
        except (BotoCoreError, ClientError, ValueError) as exc:
            logger.error("S3 presigned URL 생성 실패: %s", exc)
            return None

    async def save_audio_to_s3(
        self,
        data: bytes,
        *,
        prefix: str,
        extension: str = ".mp3",
        content_type: str = "audio/mpeg",
        create_url: bool = False,
    ) -> Optional[Dict[str, Optional[str]]]:
        key = await self._upload_bytes_to_s3(
            data,
            prefix=prefix,
            extension=extension,
            content_type=content_type,
        )
        if not key:
            return None

        response = {"key": key, "url": None}
        if create_url:
            response["url"] = await self.generate_presigned_url(key)
        return response

    ##### 이 함수는 음성파일을 인자로 받아 stt 작업 수행하고 결과를 반환하는 함수 #####
    async def transcribe_file(self, file: UploadFile, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        파일 업로드 STT 처리
        Args:
            file: 업로드된 음성 파일
            config: STT 설정 옵션
        Returns:
            STT 전사 결과
        """
        if config is None:
            config = {
                "model_name": "sommers",
                "language": "ko",
                "use_itn": True,
                "use_disfluency_filter": False,
                "use_profanity_filter": False,
                "use_paragraph_splitter": True,
                "use_word_timestamp": True,
            }
        
        temp_path: Optional[str] = None
        s3_record: Optional[Dict[str, Optional[str]]] = None
        try:
            await file.seek(0)
            data = await file.read()
            if not data:
                raise RuntimeError("업로드된 음성 파일이 비어 있습니다.")

            extension = os.path.splitext(file.filename or "")[1] or ".mp3"
            content_type = file.content_type or "application/octet-stream"

            if self.s3_available:
                s3_record = await self.save_audio_to_s3(
                    data,
                    prefix="scenario/stt-inputs",
                    extension=extension,
                    content_type=content_type,
                )

            with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as tmp_file:
                tmp_file.write(data)
                temp_path = tmp_file.name

            result = await asyncio.to_thread(
                self.rtzr_client.transcribe_file,
                temp_path,
                config
            )
            if s3_record and s3_record.get("key"):
                metadata = result.setdefault("metadata", {})
                metadata["s3_key"] = s3_record["key"]
                if s3_record.get("url"):
                    metadata["s3_url"] = s3_record["url"]
            return result
        finally:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)
            await file.seek(0)

    def _convert_speed_to_openai(self, speed: float) -> float:
        """
        Clova Voice 스타일 속도(-5~5)를 OpenAI TTS 속도(0.25~4.0)로 변환

        Args:
            speed: Clova 스타일 속도 (-5~5) 또는 OpenAI 스타일 속도 (0.25~4.0)

        Returns:
            OpenAI TTS 속도 (0.25~4.0)
        """
        # 이미 OpenAI 범위인 경우 (0.25~4.0)
        if 0.25 <= speed <= 4.0:
            return speed

        # Clova 스타일 변환 (-5~5)
        if speed >= 0:
            # 0 (normal) -> 1.5 (약간 빠름)
            # 5 (fastest) -> 4.0 (fastest)
            openai_speed = 1.5 + (speed * 0.5)
        else:
            # -5 (slowest) -> 0.75 (느림)
            # 0 (normal) -> 1.5 (약간 빠름)
            openai_speed = 1.5 + (speed * 0.15)

        # 범위 제한
        return max(0.25, min(4.0, openai_speed))

    def _amplify_audio(self, audio_bytes: bytes, gain_db: float = 6.0) -> bytes:
        """
        오디오 볼륨을 증폭

        Args:
            audio_bytes: 원본 오디오 바이트 데이터
            gain_db: 증폭할 dB 값 (기본값 6.0dB = 약 2배)

        Returns:
            증폭된 오디오 바이트 데이터
        """
        try:
            import io
            # 바이트를 AudioSegment로 변환
            audio = AudioSegment.from_mp3(io.BytesIO(audio_bytes))

            # 볼륨 증폭
            amplified_audio = audio + gain_db

            # 다시 바이트로 변환
            output_buffer = io.BytesIO()
            amplified_audio.export(output_buffer, format="mp3")
            return output_buffer.getvalue()
        except Exception as e:
            logger.warning(f"오디오 증폭 실패, 원본 반환: {e}")
            return audio_bytes

    ##### TTS (Text-to-Speech) 관련 메서드들 #####
    async def text_to_speech(
        self,
        text: str,
        speaker: str = "alloy",  # OpenAI voices: alloy, echo, fable, onyx, nova, shimmer
        speed: float = 1.2,  # 기본값 1.2배속
        volume: int = 6,  # 볼륨 증폭 dB (0 = 원본, 6 = 약 2배, 기본값 6)
        pitch: int = 0,  # 무시됨 (OpenAI는 지원하지 않음)
        emotion: str = "neutral",  # 무시됨 (OpenAI는 지원하지 않음)
        format: str = "mp3"  # 무시됨 (OpenAI는 항상 mp3)
    ) -> bytes:
        """
        텍스트를 음성으로 변환 (OpenAI TTS 사용)
        Args:
            text: 변환할 텍스트
            speaker: 음성 종류 (alloy, echo, fable, onyx, nova, shimmer)
            speed: 음성 속도 (Clova: -5~5 또는 OpenAI: 0.25~4.0, 기본값 1.2)
            volume: 볼륨 증폭 dB (0 = 원본, 6 = 약 2배, 12 = 약 4배, 기본값 6)
            pitch: 무시됨
            emotion: 무시됨
            format: 무시됨 (항상 mp3)
        Returns:
            음성 파일 바이트 데이터 (MP3)
        """
        # 속도 변환
        openai_speed = self._convert_speed_to_openai(speed)

        audio_bytes = await asyncio.to_thread(
            self.tts_client.text_to_speech,
            text=text,
            speaker=speaker,
            speed=openai_speed
        )

        # 볼륨 증폭 (volume > 0일 때만)
        if volume > 0:
            audio_bytes = await asyncio.to_thread(
                self._amplify_audio,
                audio_bytes,
                gain_db=float(volume)
            )

        return audio_bytes
    
    async def text_to_speech_file(
        self,
        text: str,
        output_path: str,
        speaker: str = "alloy",
        speed: float = 1.2,  # 기본값 1.2배속
        volume: int = 6,  # 볼륨 증폭 dB (0 = 원본, 6 = 약 2배, 기본값 6)
        pitch: int = 0,  # 무시됨
        emotion: str = "neutral",  # 무시됨
        format: str = "mp3"  # 무시됨
    ) -> str:
        """
        텍스트를 음성 파일로 변환하여 저장 (OpenAI TTS 사용)
        Args:
            text: 변환할 텍스트
            output_path: 저장할 파일 경로
            speaker: 음성 종류 (alloy, echo, fable, onyx, nova, shimmer)
            speed: 음성 속도 (Clova: -5~5 또는 OpenAI: 0.25~4.0, 기본값 1.2)
            volume: 볼륨 증폭 dB (0 = 원본, 6 = 약 2배, 12 = 약 4배, 기본값 6)
            pitch: 무시됨
            emotion: 무시됨
            format: 무시됨
        Returns:
            저장된 파일 경로
        """
        # 속도 변환
        openai_speed = self._convert_speed_to_openai(speed)

        audio_bytes = await asyncio.to_thread(
            self.tts_client.text_to_speech,
            text=text,
            speaker=speaker,
            speed=openai_speed
        )

        # 볼륨 증폭 (volume > 0일 때만)
        if volume > 0:
            audio_bytes = await asyncio.to_thread(
                self._amplify_audio,
                audio_bytes,
                gain_db=float(volume)
            )

        # 디렉토리가 없으면 생성
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # 파일로 저장
        with open(output_path, "wb") as f:
            f.write(audio_bytes)

        return output_path




'''1. 마이크 입력 → 오디오 데이터
2. 오디오 데이터 → gRPC 채널 → 리턴제로 서버
3. 리턴제로 서버 → STT 처리 → 텍스트 변환
4. 텍스트 → 클라이언트로 반환
'''
def _check_microphone_available():
    """마이크가 사용 가능한지 확인 (로컬 환경에서만 가능)"""
    try:
        test_audio = pyaudio.PyAudio()
        device_count = test_audio.get_device_count()
        test_audio.terminate()
        
        # 디바이스가 0개이면 마이크 없음
        if device_count == 0:
            return False
        
        # 입력 디바이스 확인
        test_audio = pyaudio.PyAudio()
        for i in range(device_count):
            dev_info = test_audio.get_device_info_by_index(i)
            if dev_info.get('maxInputChannels') > 0:
                test_audio.terminate()
                return True
        test_audio.terminate()
        return False
    except Exception as e:
        print(f"마이크 확인 중 오류: {e}")
        return False

class MicrophoneStream:
    #Recording Stream을 생성하고 오디오 청크를 생성하는 제너레이터를 반환하는 클래스.

    def __init__(self: object, rate: int = SAMPLE_RATE, chunk: int = CHUNK, channels: int = CHANNELS, format = FORMAT) -> None:
        self._rate = rate
        self._chunk = chunk
        self._channels = channels
        self._format = format

        # Create a thread-safe buffer of audio data
        self._buff = queue.Queue()
        self.closed = True

        # 마이크 사용 가능 여부 확인
        if not _check_microphone_available():
            raise RuntimeError(
                "마이크가 감지되지 않습니다. Docker 환경에서는 마이크를 사용할 수 없습니다. "
                "로컬 환경에서만 실시간 STT를 사용할 수 있습니다."
            )

        self._audio_interface = pyaudio.PyAudio()
        self._audio_stream = self._audio_interface.open(
            format=pyaudio.paInt16,
            channels=self._channels,
            rate=self._rate,
            input=True,
            frames_per_buffer=self._chunk,
            stream_callback=self._fill_buffer,
        )
        self.closed = False
    
    def terminate(self: object,) -> None:
        """
        Stream을 닫고, 제너레이터를 종료하는 함수
        """
        self._audio_stream.stop_stream()
        self._audio_stream.close()
        self.closed = True
        self._buff.put(None)
        self._audio_interface.terminate()
        
    def _fill_buffer(self: object, in_data: object, frame_count: int, time_info: object, status_flags: object) -> object: 
        """
        오디오 Stream으로부터 데이터를 수집하고 버퍼에 저장하는 콜백 함수. 마이크에 오디오가 들어오면 자동 호출

        Args:
            in_data: 바이트 오브젝트로 된 오디오 데이터
            frame_count: 프레임 카운트
            time_info: 시간 정보
            status_flags: 상태 플래그

        Returns:
            바이트 오브젝트로 된 오디오 데이터
        """
        self._buff.put(in_data) # 오디오 데이터를 버퍼에 저장 
        return None, pyaudio.paContinue   #계속 진행
    
    def generator(self: object) -> object:
        """
        Stream으로부터 오디오 청크를 생성하는 Generator. => 오디오 데이터를 실시간으로 생성!! 

        Args:
            self: The MicrophoneStream object

        Returns:
            오디오 청크를 생성하는 Generator
        """
        while not self.closed:
            chunk = self._buff.get() # 큐에서 오디오 데이터 가져오기 
            if chunk is None:
                return
            data = [chunk]

            while True:
                try:
                    chunk = self._buff.get(block=False)
                    if chunk is None:
                        return
                    data.append(chunk)
                except queue.Empty:
                    break

            yield b"".join(data)  # 오디오 데이터 반환


class OpenAITTSClient:
    """OpenAI TTS 클라이언트"""
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.api_url = "https://api.openai.com/v1/audio/speech"
        self._sess = RequestsSession()

    def _get_headers(self) -> Dict[str, str]:
        """인증 헤더 반환"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def text_to_speech(
        self,
        text: str,
        speaker: str = "alloy",  # OpenAI voices: alloy, echo, fable, onyx, nova, shimmer
        speed: float = 1.0,  # 0.25 to 4.0
        **kwargs  # 나머지 파라미터는 무시 (호환성 유지)
    ) -> bytes:
        """
        텍스트를 음성으로 변환 (OpenAI TTS)

        Args:
            text: 변환할 텍스트
            speaker: 음성 종류 (alloy, echo, fable, onyx, nova, shimmer)
            speed: 음성 속도 (0.25 ~ 4.0, 기본값 1.0)

        Returns:
            음성 파일 바이트 데이터 (MP3)
        """
        if not self.api_key:
            raise ValueError("OpenAI API 키가 설정되지 않았습니다.")

        # OpenAI 지원 voice 목록
        valid_voices = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
        if speaker not in valid_voices:
            logger.warning(f"지원하지 않는 voice: {speaker}, 기본값 'alloy' 사용")
            speaker = "alloy"

        # speed 범위 검증
        speed = max(0.25, min(4.0, speed))

        payload = {
            "model": "tts-1",  # tts-1 또는 tts-1-hd
            "input": text,
            "voice": speaker,
            "speed": speed
        }

        headers = self._get_headers()

        try:
            logger.debug(f"OpenAI TTS 요청 URL: {self.api_url}")
            logger.debug(f"OpenAI TTS 요청 데이터: {payload}")

            response = self._sess.post(
                self.api_url,
                headers=headers,
                json=payload
            )

            logger.debug(f"OpenAI TTS 응답 상태 코드: {response.status_code}")

            if response.status_code != 200:
                logger.error(f"OpenAI TTS API 오류 응답: {response.text}")

            response.raise_for_status()
            return response.content

        except Exception as e:
            logger.error(f"OpenAI TTS 오류: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"오류 응답 내용: {e.response.text}")
            raise

    def text_to_speech_file(
        self,
        text: str,
        output_path: str,
        speaker: str = "alloy",
        speed: float = 1.0,
        **kwargs  # 나머지 파라미터는 무시 (호환성 유지)
    ) -> str:
        """
        텍스트를 음성 파일로 변환하여 저장

        Args:
            text: 변환할 텍스트
            output_path: 저장할 파일 경로
            speaker: 음성 종류
            speed: 음성 속도

        Returns:
            저장된 파일 경로
        """
        audio_data = self.text_to_speech(
            text=text,
            speaker=speaker,
            speed=speed
        )

        # 디렉토리가 없으면 생성
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        with open(output_path, "wb") as f:
            f.write(audio_data)

        return output_path


class ClovaVoiceTTSClient:
    """CLOVA VOICE TTS 클라이언트"""
    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.api_url = "https://naveropenapi.apigw.ntruss.com/tts-premium/v1/tts"
        self._sess = RequestsSession()
    
    def _get_headers(self) -> Dict[str, str]:
        """인증 헤더 반환"""
        return {
            "X-NCP-APIGW-API-KEY-ID": self.client_id,
            "X-NCP-APIGW-API-KEY": self.client_secret,
            "Content-Type": "application/x-www-form-urlencoded"
        }
    
    def text_to_speech(
        self, 
        text: str, 
        speaker: str = "nara", 
        speed: int = 0, 
        volume: int = 0,
        pitch: int = 0,
        emotion: str = "neutral",
        format: str = "mp3"
    ) -> bytes:
        """
        텍스트를 음성으로 변환
        
        Args:
            text: 변환할 텍스트
            speaker: 음성 종류 (nara, jinho, miju, nhajun, ndain, nmeimei, njinho, njiyun, njihun, njinseok, nseongjin, ntaeho, nyoungmi, nyoungjin, nyoungsook, nyoungsun, nyoungwoo, nyoungyoon, nyoungzoo, nyoungzoo2, nyoungzoo3, nyoungzoo4, nyoungzoo5, nyoungzoo6, nyoungzoo7, nyoungzoo8, nyoungzoo9, nyoungzoo10)
            speed: 음성 속도 (-5 ~ 5)
            volume: 음성 볼륨 (-5 ~ 5)
            pitch: 음성 피치 (-5 ~ 5)
            emotion: 감정 (neutral, happy, sad, angry, fearful, surprised, disgusted)
            format: 출력 형식 (mp3, wav)
            
        Returns:
            음성 파일 바이트 데이터
        """
        if self.client_id == "NONE" or self.client_secret == "NONE":
            raise ValueError("CLOVA VOICE API 키가 설정되지 않았습니다.")
        
        # speaker 파라미터 검증
        if not speaker or speaker.strip() == "":
            raise ValueError("speaker 파라미터가 필요합니다.")
        
        # CLOVA VOICE TTS API는 form-encoded 형식으로 요청 (speaker가 맨 앞, text가 맨 뒤)
        data = {
            "speaker": speaker,
            "volume": volume,
            "speed": speed,
            "pitch": pitch,
            "format": format,
            "text": text
        }
        
        # emotion 파라미터는 지원되는 경우에만 추가
        if emotion and emotion != "neutral":
            data["emotion"] = emotion
        
        headers = self._get_headers()
        
        try:
            logger.debug(f"TTS 요청 URL: {self.api_url}")
            logger.debug(f"TTS 요청 헤더: {headers}")
            logger.debug(f"TTS 요청 데이터: {data}")
            
            response = self._sess.post(
                self.api_url,
                headers=headers,
                data=data
            )
            
            logger.debug(f"TTS 응답 상태 코드: {response.status_code}")
            logger.debug(f"TTS 응답 헤더: {dict(response.headers)}")
            
            if response.status_code != 200:
                logger.error(f"TTS API 오류 응답: {response.text}")
            
            response.raise_for_status()
            return response.content
            
        except Exception as e:
            logger.error(f"CLOVA VOICE TTS 오류: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"오류 응답 내용: {e.response.text}")
            raise
    
    def text_to_speech_file(
        self, 
        text: str, 
        output_path: str,
        speaker: str = "nara", 
        speed: int = 0, 
        volume: int = 0,
        pitch: int = 0,
        emotion: str = "neutral",
        format: str = "mp3"
    ) -> str:
        """
        텍스트를 음성 파일로 변환하여 저장
        
        Args:
            text: 변환할 텍스트
            output_path: 저장할 파일 경로
            speaker: 음성 종류
            speed: 음성 속도 (-5 ~ 5)
            volume: 음성 볼륨 (-5 ~ 5)
            pitch: 음성 피치 (-5 ~ 5)
            emotion: 감정
            format: 출력 형식 (mp3, wav)
            
        Returns:
            저장된 파일 경로
        """
        audio_data = self.text_to_speech(
            text=text,
            speaker=speaker,
            speed=speed,
            volume=volume,
            pitch=pitch,
            emotion=emotion,
            format=format
        )
        
        # 디렉토리가 없으면 생성
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, "wb") as f:
            f.write(audio_data)
        
        return output_path


class RTZROpenAPIClient:
    def __init__(self, client_id, client_secret):
        super().__init__()
        self._logger = logging.getLogger(__name__)
        self.client_id = client_id
        self.client_secret = client_secret
        self._sess = RequestsSession()
        self._token = None
        self._stream = None

    @property #함수를 속성처럼
    def token(self):#api사용을 위한 토큰 발급 함수 token 만료기간 6시간
        logger.debug(f"self._token 상태: {self._token}")
        
        if self._token is None:
            logger.debug("_token이 None입니다. 새로 발급받습니다.")
        elif self._token["expire_at"] < time.time():
            logger.debug(f"토큰 만료됨. 만료 시간: {self._token['expire_at']}, 현재 시간: {time.time()}")
        
        if self._token is None or self._token["expire_at"] < time.time():
            logger.info("API 인증 시도 중...")
            logger.debug(f"client_id: {self.client_id}")
            logger.debug(f"client_secret: {'*' * len(self.client_secret)} (길이: {len(self.client_secret)})")
            logger.debug(f"API URL: {API_BASE}/v1/authenticate")
            
            try:
                resp = self._sess.post(
                    API_BASE + "/v1/authenticate",
                    data={"client_id": self.client_id, "client_secret": self.client_secret},
                )
                logger.debug(f"응답 상태 코드: {resp.status_code}")
                logger.debug(f"응답 헤더: {dict(resp.headers)}")
                logger.debug(f"응답 본문: {resp.text}")
                
                resp.raise_for_status()
                self._token = resp.json()
                logger.debug(f"발급받은 토큰: {self._token}")
                logger.info("토큰 발급 성공!")
                logger.info(f"토큰 만료 시간: {self._token.get('expire_at', 'N/A')}")
                
            except Exception as e:
                logger.error(f"API 인증 오류: {e}")
                logger.error(f"응답 내용: {resp.text if 'resp' in locals() else 'N/A'}")
                raise  # 에러를 다시 발생시켜 디버깅 가능하게
        
        logger.debug(f"반환할 토큰: {self._token.get('access_token', 'None')[:50]}...")
        return self._token["access_token"]
    
    def _auth_headers(self) -> Dict[str, str]:
        """인증 헤더 반환"""
        return {"Authorization": f"Bearer {self.token}"}

    def transcribe_streaming_grpc(self, config):
        logger.info("STT 시작...")
        logger.debug(f"gRPC 서버: {GRPC_SERVER_URL}")
        
        # 스트림 초기화
        self._stream = MicrophoneStream(SAMPLE_RATE, CHUNK, CHANNELS, FORMAT)
        
        base = GRPC_SERVER_URL
        with grpc.secure_channel(base, credentials=grpc.ssl_channel_credentials()) as channel: #with 문법 -> file 열때 열린 파일을 자동으로 닫아줌, 서버 연결 부분
            logger.info("gRPC 채널 연결 성공!")
            stub = pb_grpc.OnlineDecoderStub(channel) # STT 서비스 스텁
            logger.info("STT 서비스 스텁 생성 완료!")
            
            cred = grpc.access_token_call_credentials(self.token)  #인증 토큰
            logger.info("인증 토큰 설정 완료!") 

            audio_generator = self._stream.generator() # 마이크에서 오디오 데이터

            def req_iterator():
                yield pb.DecoderRequest(streaming_config=config)  # 설정 전송
                
                for chunk in audio_generator: # 마이크에서 오디오 데이터
                    yield pb.DecoderRequest(audio_content=chunk) # chunk(데이터)를 넘겨서, 스트리밍 STT 수행
                

            req_iter = req_iterator()
            resp_iter = stub.Decode(req_iter, credentials=cred)

            for resp in resp_iter: # stt 결과 받기
                resp: pb.DecoderResponse
                for res in resp.results:
										# 실시간 출력 형태를 위해서 캐리지 리턴 이용
                    if not res.is_final:
                        print("\033[K"+"Text: {}".format(res.alternatives[0].text), end="\r", flush=True) # \033[K: clear line Escape Sequence
                    else:
                        print("\033[K" + "Text: {}".format(res.alternatives[0].text), end="\n")
                        
    ##### 이 함수는 음성파일을 인자로 받아 stt 작업 수행하고 결과를 반환하는 함수 #####
    def transcribe_file(self, file_path: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        파일 업로드 STT API 호출 (일반 STT)
        
        Args:
            file_path: 음성 파일 경로
            config: STT 설정
            
        Returns:
            전사 결과
        """
        url = f"{API_BASE}/v1/transcribe"
        
        with open(file_path, "rb") as f:
            files = {"file": (os.path.basename(file_path), f)}
            data = {"config": json.dumps(config)}
            resp = self._sess.post(
                url,
                headers=self._auth_headers(),
                files=files,
                data=data
            )
            resp.raise_for_status()
            return resp.json()
    
    def get_transcription(self, transcribe_id: str) -> Dict[str, Any]:
        """
        전사 결과 조회
        
        Args:
            transcribe_id: 전사 ID
            
        Returns:
            전사 결과 상태 및 데이터
        """
        url = f"{API_BASE}/v1/transcribe/{transcribe_id}"
        resp = self._sess.get(url, headers=self._auth_headers())
        resp.raise_for_status()
        return resp.json()
    
    def wait_for_result(
        self,
        transcribe_id: str,
        poll_interval_sec: int = 5,
        timeout_sec: int = 3600,
    ) -> Dict[str, Any]:
        """
        전사 결과가 완료될 때까지 대기
        
        Args:
            transcribe_id: 전사 ID
            poll_interval_sec: 폴링 간격 (초)
            timeout_sec: 타임아웃 (초)
            
        Returns:
            최종 전사 결과
        """
        deadline = time.time() + timeout_sec
        while True:
            if time.time() > deadline:
                raise TimeoutError("전사 결과 대기 시간 초과")
            
            result = self.get_transcription(transcribe_id)
            status = result.get("status")
            
            if status in ("completed", "failed"):
                return result
            
            time.sleep(poll_interval_sec)
    
    def __del__(self):
        if self._stream:
            self._stream.terminate()







class LLMClient:
    """LLM API 클라이언트 (OpenAI 호환) - 간단한 텍스트 입력/출력"""
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: int = 60,
        max_retries: int = 3
    ):
        """
        LLM 클라이언트 초기화
        
        Args:
            api_key: API 키
            base_url: API 베이스 URL (기본값: OpenAI API)
            model: 사용할 모델명 (기본값: gpt-4o-mini)
            timeout: 요청 타임아웃 (초)
            max_retries: 최대 재시도 횟수
        """
        self.api_key = api_key or OPENAI_API_KEY
        self.base_url = base_url or OPENAI_BASE_URL
        self.model = model or OPENAI_MODEL
        self.timeout = timeout
        self.max_retries = max_retries
        self._client = httpx.AsyncClient(timeout=timeout)
        
        if not self.api_key:
            logger.warning("LLM API 키가 설정되지 않았습니다. LLM 기능을 사용할 수 없습니다.")
    
    def _get_headers(self) -> Dict[str, str]:
        """인증 헤더 반환"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    async def generate_text(
        self,
        prompt: str,
        prompt_role: str = "user",
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = 1000
    ) -> Dict[str, Any]:
        """
        텍스트 입력 -> 텍스트 출력 (전체 응답 정보 포함)
        
        Args:
            prompt: 입력 텍스트 (프롬프트)
            prompt_role: prompt의 role (기본값: "user", 가능한 값: "user", "assistant", "system")
            model: 사용할 모델 (None이면 기본 모델 사용)
            temperature: 온도 파라미터 (0.0 ~ 2.0)
            max_tokens: 최대 토큰 수 (기본값: 1000)
            
        Returns:
            전체 응답 정보를 포함한 딕셔너리
            {
                "generated_text": 생성된 텍스트,
                "model": 사용된 모델명,
                "max_tokens": 사용된 max_tokens 값,
                "usage": 토큰 사용량 정보,
                "finish_reason": 완료 이유,
                "full_response": 전체 API 응답
            }
        """
        if not self.api_key:
            raise ValueError("LLM API 키가 설정되지 않았습니다.")
        
        # role 검증
        valid_roles = ["system", "user", "assistant"]
        if prompt_role not in valid_roles:
            raise ValueError(f"prompt_role은 다음 중 하나여야 합니다: {valid_roles}")
        
        # 실제 사용될 값 계산
        actual_model = model or self.model
        actual_max_tokens = max_tokens if max_tokens is not None else 1000
        
        # 메시지 구성
        messages = [{"role": prompt_role, "content": prompt}]
        
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": actual_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": actual_max_tokens
        }
        
        headers = self._get_headers()
        
        for attempt in range(self.max_retries):
            try:
                logger.debug(f"LLM API 호출 시도 {attempt + 1}/{self.max_retries}")
                logger.debug(f"URL: {url}")
                logger.debug(f"Model: {payload['model']}")
                
                response = await self._client.post(
                    url,
                    headers=headers,
                    json=payload
                )
                
                response.raise_for_status()
                result = response.json()
                
                # 전체 응답 정보 반환
                choice = result["choices"][0]
                return {
                    "generated_text": choice["message"]["content"],
                    "model": result.get("model", actual_model),
                    "max_tokens": actual_max_tokens,
                    "usage": result.get("usage", {}),
                    "finish_reason": choice.get("finish_reason"),
                    "full_response": result
                }
                
            except httpx.HTTPStatusError as e:
                logger.error(f"LLM API HTTP 오류: {e.response.status_code} - {e.response.text}")
                if attempt == self.max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)  # 지수 백오프
                
            except httpx.RequestError as e:
                logger.error(f"LLM API 요청 오류: {e}")
                if attempt == self.max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)
    
    async def close(self):
        """클라이언트 종료"""
        await self._client.aclose()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()



from openai import AsyncOpenAI
class LLMService:
    """LLM 서비스 클라이언트 (공통 인터페이스)"""
    def __init__(self, db: Session):
        self.db = db
        self._llm_client: Optional[AsyncOpenAI] = None
    
    @property
    def client(self) -> AsyncOpenAI:
        if self._llm_client is None:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY 환경 변수가 설정되어 있지 않습니다.")
            self._llm_client = AsyncOpenAI(api_key=api_key)
        return self._llm_client
    
    async def generate_text(
        self,
        prompt: str,
        prompt_role: str = "user",
        model: Optional[str] = None,
        max_tokens: Optional[int] = 3000
    ) -> Dict[str, Any]:
        response = await self.client.chat.completions.create(
            model=model or "gpt-4o-mini",
            messages=[{"role": prompt_role, "content": prompt}],
            max_tokens=max_tokens,
        )

        return {
            "content": response.choices[0].message.content,
            "usage": response.usage,
        }



if __name__ ==  "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    load_dotenv()

    client_id = os.getenv("RETURN_ZERO_CLIENT_ID")
    logger.debug(f"CLIENT_ID: {CLIENT_ID}")
    client_secret = os.getenv("RETURN_ZERO_CLIENT_SECRET")

    if not client_id or not client_secret:
        logger.error("환경변수 RETURN_ZERO_CLIENT_ID, RETURN_ZERO_CLIENT_SECRET를 설정해주세요.")
        exit(1)
    

    #STT 설정
    config = pb.DecoderConfig(
        sample_rate=SAMPLE_RATE,
        encoding=ENCODING,
        use_itn=True,
        use_disfluency_filter=False,
        use_profanity_filter=False,
    )

    client = RTZROpenAPIClient(client_id, client_secret)
    try:
        logger.info("실시간 STT를 시작합니다. Ctrl+C로 종료하세요.")
        client.transcribe_streaming_grpc(config)
    except KeyboardInterrupt:
        logger.info("Program terminated by user.")
        del client
