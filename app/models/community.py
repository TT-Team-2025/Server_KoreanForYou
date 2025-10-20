"""
커뮤니티 관련 모델
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
import enum


class PostCategory(str, enum.Enum):
    """게시글 카테고리"""
    QNA = "Q&A"
    INFO_SHARE = "정보공유"
    FREE = "자유게시판"
    JOB_INFO = "취업정보"


class Post(Base):
    """게시글 테이블"""
    __tablename__ = "posts"
    
    post_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    category = Column(Enum(PostCategory), nullable=False, default=PostCategory.FREE)
    view_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # 관계 설정
    user = relationship("User", back_populates="posts")
    replies = relationship("Reply", back_populates="post")


class Reply(Base):
    """댓글 테이블"""
    __tablename__ = "replies"
    
    reply_id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.post_id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # 관계 설정
    post = relationship("Post", back_populates="replies")
    user = relationship("User", back_populates="replies")
