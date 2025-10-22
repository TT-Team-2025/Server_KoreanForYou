"""
사용자 관련 스키마
"""
from pydantic import BaseModel, EmailStr, validator
from typing import Optional
from datetime import datetime


# 사용자 기본 정보
class UserBase(BaseModel):
    email: EmailStr
    nickname: Optional[str] = None
    nationality: Optional[str] = None
    job_id: Optional[int] = None
    level_id: Optional[int] = None


class UserCreate(UserBase):
    password: str
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('비밀번호는 최소 8자 이상이어야 합니다')
        return v


class UserUpdate(BaseModel):
    nickname: Optional[str] = None
    nationality: Optional[str] = None
    job_id: Optional[int] = None
    level_id: Optional[int] = None
    theme: Optional[str] = None


class UserPasswordChange(BaseModel):
    current_password: str
    new_password: str
    
    @validator('new_password')
    def validate_new_password(cls, v):
        if len(v) < 8:
            raise ValueError('새 비밀번호는 최소 8자 이상이어야 합니다')
        return v


class UserLanguageChange(BaseModel):
    level_id: int


class UserJobChange(BaseModel):
    job_id: int


class UserThemeChange(BaseModel):
    theme: str
    
    @validator('theme')
    def validate_theme(cls, v):
        allowed_themes = ['light', 'dark', 'auto']
        if v not in allowed_themes:
            raise ValueError(f'테마는 {", ".join(allowed_themes)} 중 하나여야 합니다')
        return v


class UserResponse(UserBase):
    user_id: int
    profile_img: Optional[str] = None
    theme: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class UserStatusResponse(BaseModel):
    user_id: int
    total_study_time: int
    total_sentences_completed: int
    total_scenarios_completed: int
    average_score: Optional[float] = None
    current_access_days: int
    longest_access_days: int
    last_study_date: Optional[datetime] = None
    
    class Config:
        from_attributes = True


# 인증 관련
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class SignupRequest(UserCreate):
    pass


class TokenData(BaseModel):
    user_id: int
    email: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str


# 직무 관련
class JobBase(BaseModel):
    job_name: str
    description: Optional[str] = None


class JobCreate(JobBase):
    pass


class JobResponse(JobBase):
    job_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True


# 레벨 관련
class UserLevelBase(BaseModel):
    level_name: str
    description: Optional[str] = None


class UserLevelCreate(UserLevelBase):
    pass


class UserLevelResponse(UserLevelBase):
    level_id: int
    
    class Config:
        from_attributes = True
