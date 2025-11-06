# Python 3.11 슬림 이미지 사용
FROM python:3.11-slim

WORKDIR /app

# 시스템 패키지 및 PyAudio/FFmpeg 의존성 설치
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    portaudio19-dev \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# pip 최신화 및 wheel 설치
RUN pip install --upgrade pip wheel

# 의존성 파일 복사 및 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY . .

# 환경 변수
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# 포트 노출
EXPOSE 8000

# 서버 실행 (async 최적화: workers 자동 설정)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]