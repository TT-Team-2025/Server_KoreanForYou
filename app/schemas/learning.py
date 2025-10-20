"""
학습 콘텐츠 관련 스키마
"""
from pydantic import BaseModel, validator
from typing import Optional, List, Dict, Any
from datetime import datetime


# 학습 카테고리 관련
class LearningCategoryBase(BaseModel):
    job_id: int
    title: str
    sub_title: str = "모든 직무 공통"


class LearningCategoryCreate(LearningCategoryBase):
    pass


class LearningCategoryResponse(LearningCategoryBase):
    category_id: int
    
    class Config:
        from_attributes = True


# 챕터 관련
class ChapterBase(BaseModel):
    category_id: int
    job_id: Optional[int] = None
    level_id: int
    title: str
    description: Optional[str] = None
    is_active: bool = True
    
    @validator('title')
    def validate_title(cls, v):
        if len(v) < 1 or len(v) > 200:
            raise ValueError('제목은 1-200자 사이여야 합니다')
        return v


class ChapterCreate(ChapterBase):
    pass


class ChapterUpdate(BaseModel):
    category_id: Optional[int] = None
    job_id: Optional[int] = None
    level_id: Optional[int] = None
    title: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    
    @validator('title')
    def validate_title(cls, v):
        if v is not None and (len(v) < 1 or len(v) > 200):
            raise ValueError('제목은 1-200자 사이여야 합니다')
        return v


class ChapterResponse(ChapterBase):
    chapter_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True


class ChapterListResponse(BaseModel):
    chapters: List[ChapterResponse]
    total: int
    page: int
    size: int


# 문장 관련
class SentenceBase(BaseModel):
    chapter_id: int
    content: str
    translated_content: Optional[str] = None
    tts_url: Optional[str] = None
    
    @validator('content')
    def validate_content(cls, v):
        if len(v) < 1 or len(v) > 500:
            raise ValueError('문장 내용은 1-500자 사이여야 합니다')
        return v


class SentenceCreate(SentenceBase):
    pass


class SentenceUpdate(BaseModel):
    chapter_id: Optional[int] = None
    content: Optional[str] = None
    translated_content: Optional[str] = None
    tts_url: Optional[str] = None
    
    @validator('content')
    def validate_content(cls, v):
        if v is not None and (len(v) < 1 or len(v) > 500):
            raise ValueError('문장 내용은 1-500자 사이여야 합니다')
        return v


class SentenceResponse(SentenceBase):
    sentence_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True


class SentenceListResponse(BaseModel):
    sentences: List[SentenceResponse]
    total: int
    page: int
    size: int


# 유사 문장 관련
class SimilarSentenceBase(BaseModel):
    sentence_id: int
    content: str
    translated_content: Optional[str] = None
    similarity_type: str  # 동의어, 유사표현, 난이도조정, 상황변형


class SimilarSentenceCreate(SimilarSentenceBase):
    pass


class SimilarSentenceResponse(SimilarSentenceBase):
    similar_sentence_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True


# 챕터 피드백 관련
class ChapterFeedbackBase(BaseModel):
    user_id: int
    chapter_id: int
    total_score: Optional[int] = None
    pronunciation_score: Optional[int] = None
    accuracy_score: Optional[int] = None
    completion_time: Optional[int] = None
    total_sentences: int
    completed_sentences: int
    summary_feedback: Optional[str] = None
    weaknesses: Optional[List[str]] = None
    total_time: Optional[int] = None


class ChapterFeedbackCreate(ChapterFeedbackBase):
    pass


class ChapterFeedbackResponse(ChapterFeedbackBase):
    feedback_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True


# 문장 피드백 관련
class SentenceFeedbackBase(BaseModel):
    user_id: int
    sentence_id: int
    sentence_progress_id: int
    weaknesses: Optional[List[str]] = None


class SentenceFeedbackCreate(SentenceFeedbackBase):
    pass


class SentenceFeedbackResponse(SentenceFeedbackBase):
    feedback_id: int
    
    class Config:
        from_attributes = True
