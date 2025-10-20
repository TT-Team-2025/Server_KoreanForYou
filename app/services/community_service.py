"""
커뮤니티 관련 서비스
"""
from sqlalchemy.orm import Session
from typing import Optional, List, Tuple
from sqlalchemy import desc, asc

from app.models.community import Post, Reply
from app.schemas.community import PostCreate, PostUpdate, ReplyCreate, ReplyUpdate


class CommunityService:
    def __init__(self, db: Session):
        self.db = db
    
    def get_posts(
        self, 
        category: Optional[str] = None, 
        sort: str = "created_at",
        page: int = 1, 
        size: int = 20
    ) -> Tuple[List[Post], int]:
        """게시글 목록 조회"""
        query = self.db.query(Post)
        
        if category:
            query = query.filter(Post.category == category)
        
        # 정렬
        if sort == "created_at":
            query = query.order_by(desc(Post.created_at))
        elif sort == "view_count":
            query = query.order_by(desc(Post.view_count))
        elif sort == "title":
            query = query.order_by(asc(Post.title))
        
        total = query.count()
        posts = query.offset((page - 1) * size).limit(size).all()
        
        return posts, total
    
    def get_post_by_id(self, post_id: int) -> Optional[Post]:
        """ID로 게시글 조회"""
        return self.db.query(Post).filter(Post.post_id == post_id).first()
    
    def create_post(self, user_id: int, post_data: PostCreate) -> Post:
        """게시글 생성"""
        post = Post(
            user_id=user_id,
            **post_data.dict()
        )
        
        self.db.add(post)
        self.db.commit()
        self.db.refresh(post)
        
        return post
    
    def update_post(self, post_id: int, post_update: PostUpdate) -> Optional[Post]:
        """게시글 수정"""
        post = self.get_post_by_id(post_id)
        if not post:
            return None
        
        update_data = post_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(post, field, value)
        
        self.db.commit()
        self.db.refresh(post)
        
        return post
    
    def delete_post(self, post_id: int) -> bool:
        """게시글 삭제"""
        post = self.get_post_by_id(post_id)
        if not post:
            return False
        
        self.db.delete(post)
        self.db.commit()
        
        return True
    
    def increment_view_count(self, post_id: int) -> bool:
        """조회수 증가"""
        post = self.get_post_by_id(post_id)
        if not post:
            return False
        
        post.view_count += 1
        self.db.commit()
        
        return True
    
    def get_post_replies(
        self, 
        post_id: int, 
        page: int = 1, 
        size: int = 20
    ) -> Tuple[List[Reply], int]:
        """게시글 댓글 목록 조회"""
        query = self.db.query(Reply).filter(Reply.post_id == post_id).order_by(asc(Reply.created_at))
        
        total = query.count()
        replies = query.offset((page - 1) * size).limit(size).all()
        
        return replies, total
    
    def get_reply_by_id(self, reply_id: int) -> Optional[Reply]:
        """ID로 댓글 조회"""
        return self.db.query(Reply).filter(Reply.reply_id == reply_id).first()
    
    def create_reply(self, user_id: int, post_id: int, reply_data: ReplyCreate) -> Reply:
        """댓글 생성"""
        reply = Reply(
            user_id=user_id,
            post_id=post_id,
            **reply_data.dict()
        )
        
        self.db.add(reply)
        self.db.commit()
        self.db.refresh(reply)
        
        return reply
    
    def update_reply(self, reply_id: int, reply_update: ReplyUpdate) -> Optional[Reply]:
        """댓글 수정"""
        reply = self.get_reply_by_id(reply_id)
        if not reply:
            return None
        
        update_data = reply_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(reply, field, value)
        
        self.db.commit()
        self.db.refresh(reply)
        
        return reply
    
    def delete_reply(self, reply_id: int) -> bool:
        """댓글 삭제"""
        reply = self.get_reply_by_id(reply_id)
        if not reply:
            return False
        
        self.db.delete(reply)
        self.db.commit()
        
        return True
