"""
커뮤니티 관련 서비스
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, asc
from typing import Optional, List, Tuple

from app.models.community import Post, Reply
from app.schemas.community import PostCreate, PostUpdate, ReplyCreate, ReplyUpdate


class CommunityService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_posts(
        self,
        category: Optional[str] = None,
        sort: str = "created_at",
        page: int = 1,
        size: int = 20
    ) -> Tuple[List[Post], int]:
        """게시글 목록 조회"""
        stmt = select(Post)

        if category:
            stmt = stmt.where(Post.category == category)

        # 정렬
        if sort == "created_at":
            stmt = stmt.order_by(desc(Post.created_at))
        elif sort == "view_count":
            stmt = stmt.order_by(desc(Post.view_count))
        elif sort == "title":
            stmt = stmt.order_by(asc(Post.title))

        # 전체 개수
        count_stmt = select(func.count()).select_from(stmt.alias())
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar() or 0

        # 페이징
        stmt = stmt.offset((page - 1) * size).limit(size)
        result = await self.db.execute(stmt)
        posts = list(result.scalars().all())

        return posts, total
    
    async def get_post_by_id(self, post_id: int) -> Optional[Post]:
        """ID로 게시글 조회"""
        result = await self.db.execute(select(Post).where(Post.post_id == post_id))
        return result.scalar_one_or_none()

    async def create_post(self, user_id: int, post_data: PostCreate) -> Post:
        """게시글 생성"""
        post = Post(
            user_id=user_id,
            **post_data.model_dump()
        )

        self.db.add(post)
        await self.db.commit()
        await self.db.refresh(post)
        
        return post
    
    async def update_post(self, post_id: int, post_update: PostUpdate) -> Optional[Post]:
        """게시글 수정"""
        post = await self.get_post_by_id(post_id)
        if not post:
            return None
        
        update_data = post_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(post, field, value)

        await self.db.commit()
        await self.db.refresh(post)
        
        return post
    
    async def delete_post(self, post_id: int) -> bool:
        """게시글 삭제"""
        post = await self.get_post_by_id(post_id)
        if not post:
            return False
        
        await self.db.delete(post)
        await self.db.commit()
        
        return True
    
    async def increment_view_count(self, post_id: int) -> bool:
        """조회수 증가"""
        post = await self.get_post_by_id(post_id)
        if not post:
            return False
        
        post.view_count += 1
        await self.db.commit()
        
        return True
    
    async def get_post_replies(
        self,
        post_id: int,
        page: int = 1,
        size: int = 20
    ) -> Tuple[List[Reply], int]:
        """게시글 댓글 목록 조회"""
        stmt = select(Reply).where(Reply.post_id == post_id).order_by(asc(Reply.created_at))

        # 전체 개수
        count_stmt = select(func.count()).select_from(stmt.alias())
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar() or 0

        # 페이징
        stmt = stmt.offset((page - 1) * size).limit(size)
        result = await self.db.execute(stmt)
        replies = list(result.scalars().all())

        return replies, total

    async def get_reply_by_id(self, reply_id: int) -> Optional[Reply]:
        """ID로 댓글 조회"""
        result = await self.db.execute(select(Reply).where(Reply.reply_id == reply_id))
        return result.scalar_one_or_none()

    async def create_reply(self, user_id: int, post_id: int, reply_data: ReplyCreate) -> Reply:
        """댓글 생성"""
        reply = Reply(
            user_id=user_id,
            post_id=post_id,
            **reply_data.model_dump()
        )

        self.db.add(reply)
        await self.db.commit()
        await self.db.refresh(reply)
        
        return reply
    
    async def update_reply(self, reply_id: int, reply_update: ReplyUpdate) -> Optional[Reply]:
        """댓글 수정"""
        reply = await self.get_reply_by_id(reply_id)
        if not reply:
            return None
        
        update_data = reply_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(reply, field, value)

        await self.db.commit()
        await self.db.refresh(reply)
        
        return reply
    
    async def delete_reply(self, reply_id: int) -> bool:
        """댓글 삭제"""
        reply = await self.get_reply_by_id(reply_id)
        if not reply:
            return False
        
        await self.db.delete(reply)
        await self.db.commit()
        
        return True
