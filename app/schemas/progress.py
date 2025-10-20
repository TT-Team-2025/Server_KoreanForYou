"""
학습 진행 상황 관련 스키마
"""
from pydantic import BaseModel, validator
from typing import Optional, List
from datetime import datetime
from decimal import Decimal


# 사용자 진행 상황 관련
class UserProgressBase(BaseModel):
    user_id: int
    chapter_id: int
    completion_rate: Decimal
    last_access_at: Optional[datetime] = None


class UserProgressCreate(UserProgressBase):
    pass


class UserProgressUpdate(BaseModel):
    completion_rate: Optional[Decimal] = None
    last_access_at: Optional[datetime] = None


class UserProgressResponse(UserProgressBase):
    progress_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True


# 문장 진행 상황 관련
class SentenceProgressBase(BaseModel):
    user_id: int
    sentence_id: int
    is_completed: bool = False
    stt_audio_url: Optional[str] = None
    stt_transcript: Optional[str] = None
    total_word_count: Optional[int] = None
    correct_word_count: Optional[int] = None
    recognized_word_count: Optional[int] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


class SentenceProgressCreate(SentenceProgressBase):
    pass


class SentenceProgressUpdate(BaseModel):
    is_completed: Optional[bool] = None
    stt_audio_url: Optional[str] = None
    stt_transcript: Optional[str] = None
    total_word_count: Optional[int] = None
    correct_word_count: Optional[int] = None
    recognized_word_count: Optional[int] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


class SentenceProgressResponse(SentenceProgressBase):
    progress_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True


# 진행률 통계 관련
class ProgressStatsResponse(BaseModel):
    total_chapters: int
    completed_chapters: int
    total_sentences: int
    completed_sentences: int
    overall_progress: Decimal
    study_time_minutes: int
    last_study_date: Optional[datetime] = None


class ChapterProgressResponse(BaseModel):
    chapter_id: int
    chapter_title: str
    completion_rate: Decimal
    total_sentences: int
    completed_sentences: int
    last_access_at: Optional[datetime] = None


class UserProgressHistoryResponse(BaseModel):
    user_id: int
    progress_history: List[ChapterProgressResponse]
    total_study_time: int
    total_sentences_completed: int
    average_score: Optional[Decimal] = None
