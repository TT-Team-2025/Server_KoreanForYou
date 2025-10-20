"""
커뮤니티 관련 스키마
"""
from pydantic import BaseModel, validator
from typing import Optional, List
from datetime import datetime
from enum import Enum


class PostCategory(str, Enum):
    QNA = "Q&A"
    INFO_SHARE = "정보공유"
    FREE = "자유게시판"
    JOB_INFO = "취업정보"


# 게시글 관련
class PostBase(BaseModel):
    title: str
    content: str
    category: PostCategory = PostCategory.FREE
    
    @validator('title')
    def validate_title(cls, v):
        if len(v) < 1 or len(v) > 200:
            raise ValueError('제목은 1-200자 사이여야 합니다')
        return v
    
    @validator('content')
    def validate_content(cls, v):
        if len(v) < 1:
            raise ValueError('내용은 최소 1자 이상이어야 합니다')
        return v


class PostCreate(PostBase):
    pass


class PostUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    category: Optional[PostCategory] = None
    
    @validator('title')
    def validate_title(cls, v):
        if v is not None and (len(v) < 1 or len(v) > 200):
            raise ValueError('제목은 1-200자 사이여야 합니다')
        return v
    
    @validator('content')
    def validate_content(cls, v):
        if v is not None and len(v) < 1:
            raise ValueError('내용은 최소 1자 이상이어야 합니다')
        return v


class PostResponse(PostBase):
    post_id: int
    user_id: int
    view_count: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class PostListResponse(BaseModel):
    posts: List[PostResponse]
    total: int
    page: int
    size: int


# 댓글 관련
class ReplyBase(BaseModel):
    content: str
    
    @validator('content')
    def validate_content(cls, v):
        if len(v) < 1:
            raise ValueError('댓글 내용은 최소 1자 이상이어야 합니다')
        return v


class ReplyCreate(ReplyBase):
    pass


class ReplyUpdate(ReplyBase):
    pass


class ReplyResponse(ReplyBase):
    reply_id: int
    post_id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ReplyListResponse(BaseModel):
    replies: List[ReplyResponse]
    total: int
    page: int
    size: int
