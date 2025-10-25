"""
애플리케이션 설정 관리
"""
from pydantic_settings import BaseSettings
from typing import List, Optional
import os


class Settings(BaseSettings):
    """애플리케이션 설정"""
    
    # 기본 설정
    APP_NAME: str = "KoreanForYou"
    DEBUG: bool = False
    VERSION: str = "1.0.0"
    
    # 서버 설정
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # 데이터베이스 설정
    DATABASE_URL: str = "postgresql://user:password@localhost:5432/koreanforyou"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    
    # JWT 설정
    SECRET_KEY: str = "your-secret-key-here"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # CORS 설정
    ALLOWED_HOSTS: List[str] = ["*"]
    
    # 외부 API 설정
    TTS_API_URL: Optional[str] = None
    TTS_API_KEY: Optional[str] = None
    STT_API_URL: Optional[str] = None
    STT_API_KEY: Optional[str] = None
    LLM_API_URL: Optional[str] = None
    LLM_API_KEY: Optional[str] = None
    
    # Return Zero API 설정
    RETURN_ZERO_API_KEY: Optional[str] = None
    RETURN_ZERO_CLIENT_ID: Optional[str] = None
    RETURN_ZERO_CLIENT_SECRET: Optional[str] = None


    # AWS S3 설정
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION: str = "ap-northeast-2"
    S3_BUCKET_NAME: Optional[str] = None
    
    # Redis 설정 (캐싱용)
    REDIS_URL: Optional[str] = None
    
    # 이메일 설정
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# 전역 설정 인스턴스
settings = Settings()
