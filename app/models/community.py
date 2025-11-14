"""
커뮤니티 관련 모델
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Enum, Boolean, UniqueConstraint
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
    is_pinned = Column(Boolean, default=False, nullable=False)
    view_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # 관계 설정
    user = relationship("User", back_populates="posts")
    replies = relationship("Reply", back_populates="post")
    likes = relationship("PostLike", back_populates="post")


class Reply(Base):
    """댓글 테이블"""
    __tablename__ = "replies"
    
    reply_id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.post_id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    parent_reply_id = Column(Integer, ForeignKey("replies.reply_id"), nullable=True)
    content = Column(Text, nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # 관계 설정
    post = relationship("Post", back_populates="replies")
    user = relationship("User", back_populates="replies")
    parent_reply = relationship("Reply", remote_side=[reply_id], backref="child_replies")


class PostLike(Base):
    """게시글 좋아요 테이블"""
    __tablename__ = "post_likes"
    
    like_id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.post_id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    created_at = Column(DateTime, default=func.now())
    
    # 관계 설정
    post = relationship("Post", back_populates="likes")
    user = relationship("User", back_populates="post_likes")
    
    # user_id와 post_id의 중복 방지 (복합 유니크 제약)
    __table_args__ = (
        UniqueConstraint('user_id', 'post_id', name='uq_user_post_like'),
    )
