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

from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
import httpx
import uuid
from fastapi import UploadFile

from requests import Session as RequestsSession

from dotenv import load_dotenv

# .env 파일 로드 (최상단에서 한 번만 실행)
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

# 환경 변수 읽기 (load_dotenv()는 모듈 최상단에서 이미 호출됨)
CLIENT_ID = os.environ.get("RETURN_ZERO_CLIENT_ID")
CLIENT_SECRET = os.environ.get("RETURN_ZERO_CLIENT_SECRET")

print(f"🔍 [DEBUG] 환경 변수 로드 시도:")
print(f"🔍 [DEBUG] CLIENT_ID: {CLIENT_ID}")
print(f"🔍 [DEBUG] CLIENT_SECRET: {'*' * len(CLIENT_SECRET) if CLIENT_SECRET else 'None'}")
print(f"🔍 [DEBUG] 환경 변수 존재 여부: RETURN_ZERO_CLIENT_ID={CLIENT_ID is not None}, RETURN_ZERO_CLIENT_SECRET={CLIENT_SECRET is not None}")

# 환경 변수가 설정되지 않은 경우 경고만 출력하고 기본값 사용
if not CLIENT_ID or not CLIENT_SECRET:
    print("❌ Warning: RETURN_ZERO_CLIENT_ID and RETURN_ZERO_CLIENT_SECRET not set. Using default values.")
    CLIENT_ID = CLIENT_ID or "default_client_id"
    CLIENT_SECRET = CLIENT_SECRET or "default_client_secret"

class ExternalService:
    def __init__(self, db: Session):
        self.db = db
        self.rtzr_client = RTZROpenAPIClient(
           CLIENT_ID , 
            CLIENT_SECRET
        )

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
                "use_disfluency_filter": True,
                "use_profanity_filter": False,
                "use_paragraph_splitter": True,
                "use_word_timestamp": True,
            }
        
        # 파일을 디스크에 저장 -> 추후 s3 연동 시 삭제 필요
        upload_dir = "uploads"
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, file.filename)
        try:
            # 파일 내용을 저장
            with open(file_path, "wb") as f:
                content = await file.read()
                f.write(content)
            
            # RTZR API 호출
            result = await asyncio.to_thread(
                self.rtzr_client.transcribe_file,
                file_path,
                config
            )
            
            return result
        finally:
            # 임시 파일 삭제
            if os.path.exists(file_path):
                os.remove(file_path)

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
        print(f"🔍 [DEBUG] self._token 상태: {self._token}")
        
        if self._token is None:
            print(f"🔍 [DEBUG] _token이 None입니다. 새로 발급받습니다.")
        elif self._token["expire_at"] < time.time():
            print(f"🔍 [DEBUG] 토큰 만료됨. 만료 시간: {self._token['expire_at']}, 현재 시간: {time.time()}")
        
        if self._token is None or self._token["expire_at"] < time.time():
            print(f"🔑 API 인증 시도 중...")
            print(f"🔍 [DEBUG] client_id: {self.client_id}")
            print(f"🔍 [DEBUG] client_secret: {'*' * len(self.client_secret)} (길이: {len(self.client_secret)})")
            print(f"API URL: {API_BASE}/v1/authenticate")
            
            try:
                resp = self._sess.post(
                    API_BASE + "/v1/authenticate",
                    data={"client_id": self.client_id, "client_secret": self.client_secret},
                )
                print(f"🔍 [DEBUG] 응답 상태 코드: {resp.status_code}")
                print(f"🔍 [DEBUG] 응답 헤더: {dict(resp.headers)}")
                print(f"🔍 [DEBUG] 응답 본문: {resp.text}")
                
                resp.raise_for_status()
                self._token = resp.json()
                print(f"🔍 [DEBUG] 발급받은 토큰: {self._token}")
                print(f"✅ 토큰 발급 성공!")
                print(f"토큰 만료 시간: {self._token.get('expire_at', 'N/A')}")
                
            except Exception as e:
                print(f"❌ API 인증 오류: {e}")
                print(f"응답 내용: {resp.text if 'resp' in locals() else 'N/A'}")
                raise  # 에러를 다시 발생시켜 디버깅 가능하게
        
        print(f"🔍 [DEBUG] 반환할 토큰: {self._token.get('access_token', 'None')[:50]}...")
        return self._token["access_token"]
    
    def _auth_headers(self) -> Dict[str, str]:
        """인증 헤더 반환"""
        return {"Authorization": f"Bearer {self.token}"}

    def transcribe_streaming_grpc(self, config):
        print(f" STT 시작...")
        print(f"gRPC 서버: {GRPC_SERVER_URL}")
        
        # 스트림 초기화
        self._stream = MicrophoneStream(SAMPLE_RATE, CHUNK, CHANNELS, FORMAT)
        
        base = GRPC_SERVER_URL
        with grpc.secure_channel(base, credentials=grpc.ssl_channel_credentials()) as channel: #with 문법 -> file 열때 열린 파일을 자동으로 닫아줌, 서버 연결 부분
            print(f"🔗 gRPC 채널 연결 성공!")
            stub = pb_grpc.OnlineDecoderStub(channel) # STT 서비스 스텁
            print(f"📡 STT 서비스 스텁 생성 완료!")
            
            cred = grpc.access_token_call_credentials(self.token)  #인증 토큰
            print(f"🔐 인증 토큰 설정 완료!") 

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


if __name__ ==  "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    load_dotenv()

    client_id = os.getenv("RETURN_ZERO_CLIENT_ID")
    print(CLIENT_ID)
    client_secret = os.getenv("RETURN_ZERO_CLIENT_SECRET")

    if not client_id or not client_secret:
        print("환경변수 RETURN_ZERO_CLIENT_ID, RETURN_ZERO_CLIENT_SECRET를 설정해주세요.")
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
        print("실시간 STT를 시작합니다. Ctrl+C로 종료하세요.")
        client.transcribe_streaming_grpc(config)
    except KeyboardInterrupt:
        print("Program terminated by user.")
        del client