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
    is_pinned: bool
    view_count: int
    reply_count: int = 0  # 댓글 수
    like_count: int = 0  # 좋아요 수
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
    parent_reply_id: Optional[int] = None
    
    @validator('parent_reply_id', pre=True)
    def validate_parent_reply_id(cls, v):
        # 0이나 빈 값은 None으로 변환 (일반 댓글)
        if v is None or v == 0 or v == "":
            return None
        return v


class ReplyUpdate(ReplyBase):
    pass


class ReplyResponse(ReplyBase):
    reply_id: int
    post_id: int
    user_id: int
    parent_reply_id: Optional[int] = None
    is_deleted: bool = False
    created_at: datetime
    updated_at: datetime
    child_replies: Optional[List['ReplyResponse']] = []
    
    class Config:
        from_attributes = True


# 순환 참조 해결
ReplyResponse.model_rebuild()


# PostResponse에 replies 필드 추가 (ReplyResponse 정의 후)
class PostDetailResponse(PostResponse):
    """게시글 상세 조회 응답 (댓글 포함)"""
    replies: Optional[List[ReplyResponse]] = None


class ReplyListResponse(BaseModel):
    replies: List[ReplyResponse]
    total: int
    page: int
    size: int
