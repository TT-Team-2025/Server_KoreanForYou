"""
공통 스키마 정의
"""
from pydantic import BaseModel
from typing import Optional, List, Any, Dict
from datetime import datetime


class BaseResponse(BaseModel):
    """기본 응답 스키마"""
    success: bool = True
    message: str = "Success"
    data: Optional[Any] = None


class ErrorResponse(BaseModel):
    """에러 응답 스키마"""
    success: bool = False
    message: str
    error_code: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class PaginationParams(BaseModel):
    """페이지네이션 파라미터"""
    page: int = 1
    size: int = 20
    sort: Optional[str] = None


class PaginatedResponse(BaseModel):
    """페이지네이션 응답 스키마"""
    items: List[Any]
    total: int
    page: int
    size: int
    pages: int


class TokenResponse(BaseModel):
    """토큰 응답 스키마"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class HealthCheckResponse(BaseModel):
    """헬스 체크 응답 스키마"""
    status: str
    timestamp: datetime
    version: str
