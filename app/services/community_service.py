"""
커뮤니티 관련 서비스
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, asc, or_
from typing import Optional, List, Tuple

from app.models.community import Post, Reply, PostLike
from app.models.user import UserRole
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
        """게시글 목록 조회 (고정공지 우선 정렬)"""
        stmt = select(Post)

        if category:
            stmt = stmt.where(Post.category == category)

        # 정렬: 고정공지 우선, 그 다음 선택한 정렬 기준
        if sort == "created_at":
            stmt = stmt.order_by(desc(Post.is_pinned), desc(Post.created_at))
        elif sort == "view_count":
            stmt = stmt.order_by(desc(Post.is_pinned), desc(Post.view_count))
        elif sort == "title":
            stmt = stmt.order_by(desc(Post.is_pinned), asc(Post.title))
        else:
            # 기본값: 고정공지 우선, 생성일 내림차순
            stmt = stmt.order_by(desc(Post.is_pinned), desc(Post.created_at))

        # 전체 개수
        count_stmt = select(func.count()).select_from(stmt.alias())
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar() or 0

        # 페이징
        stmt = stmt.offset((page - 1) * size).limit(size)
        result = await self.db.execute(stmt)
        posts = list(result.scalars().all())

        # 각 게시글의 댓글 수와 좋아요 수 조회
        if posts:
            post_ids = [post.post_id for post in posts]
            
            # 댓글 수 조회
            reply_count_stmt = select(
                Reply.post_id,
                func.count(Reply.reply_id).label('reply_count')
            ).where(
                Reply.post_id.in_(post_ids)
            ).group_by(Reply.post_id)
            
            reply_count_result = await self.db.execute(reply_count_stmt)
            reply_counts = {row.post_id: row.reply_count for row in reply_count_result}
            
            # 좋아요 수 조회
            like_count_stmt = select(
                PostLike.post_id,
                func.count(PostLike.like_id).label('like_count')
            ).where(
                PostLike.post_id.in_(post_ids)
            ).group_by(PostLike.post_id)
            
            like_count_result = await self.db.execute(like_count_stmt)
            like_counts = {row.post_id: row.like_count for row in like_count_result}
            
            # 각 게시글에 댓글 수와 좋아요 수 할당 (동적 속성 추가)
            for post in posts:
                object.__setattr__(post, 'reply_count', reply_counts.get(post.post_id, 0))
                object.__setattr__(post, 'like_count', like_counts.get(post.post_id, 0))

        return posts, total
    
    #단일 조회
    async def get_post_by_id(self, post_id: int) -> Optional[Post]:
        """ID로 게시글 조회"""
        result = await self.db.execute(select(Post).where(Post.post_id == post_id))
        post = result.scalar_one_or_none()
        
        if post:
            # lazy loading 방지: 모든 필드를 명시적으로 접근하여 세션 내에서 로드
            # 세션이 만료되기 전에 모든 속성을 접근
            _ = post.post_id
            _ = post.user_id
            _ = post.title
            _ = post.content
            _ = post.category
            _ = post.is_pinned
            _ = post.view_count
            _ = post.created_at
            _ = post.updated_at
            
            # 댓글 수와 좋아요 수 조회하여 동적 속성으로 추가
            reply_count_result = await self.db.execute(
                select(func.count(Reply.reply_id)).where(Reply.post_id == post_id)
            )
            reply_count = reply_count_result.scalar() or 0
            
            like_count_result = await self.db.execute(
                select(func.count(PostLike.like_id)).where(PostLike.post_id == post_id)
            )
            like_count = like_count_result.scalar() or 0
            
            object.__setattr__(post, 'reply_count', reply_count)
            object.__setattr__(post, 'like_count', like_count)
        
        return post

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
        """게시글 삭제 (관련 댓글과 좋아요도 함께 삭제)"""
        post = await self.get_post_by_id(post_id)
        if not post:
            return False
        
        # 관련 댓글 모두 삭제 (대댓글 포함)
        replies_result = await self.db.execute(
            select(Reply).where(Reply.post_id == post_id)
        )
        replies = list(replies_result.scalars().all())
        for reply in replies:
            await self.db.delete(reply)
        
        # 관련 좋아요 모두 삭제
        likes_result = await self.db.execute(
            select(PostLike).where(PostLike.post_id == post_id)
        )
        likes = list(likes_result.scalars().all())
        for like in likes:
            await self.db.delete(like)
        
        # 게시글 삭제
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
        """게시글 댓글 목록 조회 (대댓글 포함)"""
        # 부모 댓글만 조회 (parent_reply_id가 None인 것들)
        # 삭제되지 않은 댓글이거나, 삭제되었지만 대댓글이 있는 댓글
        # 먼저 대댓글이 있는 삭제된 댓글 ID 목록 조회
        deleted_with_children_stmt = select(Reply.reply_id).where(
            Reply.post_id == post_id,
            Reply.parent_reply_id.is_(None),
            Reply.is_deleted == True
        )
        deleted_with_children_result = await self.db.execute(deleted_with_children_stmt)
        deleted_parent_ids = [row[0] for row in deleted_with_children_result]
        
        # 대댓글이 있는 삭제된 댓글 ID 확인
        if deleted_parent_ids:
            has_children_stmt = select(Reply.parent_reply_id).where(
                Reply.parent_reply_id.in_(deleted_parent_ids)
            ).distinct()
            has_children_result = await self.db.execute(has_children_stmt)
            deleted_with_children_ids = [row[0] for row in has_children_result]
        else:
            deleted_with_children_ids = []
        
        # 조회 조건: 삭제되지 않았거나, 삭제되었지만 대댓글이 있는 경우
        from sqlalchemy import or_
        conditions = [Reply.is_deleted == False]
        if deleted_with_children_ids:
            conditions.append(Reply.reply_id.in_(deleted_with_children_ids))
        
        stmt = select(Reply).where(
            Reply.post_id == post_id,
            Reply.parent_reply_id.is_(None),
            or_(*conditions)
        ).order_by(asc(Reply.created_at))

        # 전체 개수
        count_stmt = select(func.count()).select_from(stmt.alias())
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar() or 0

        # 페이징
        stmt = stmt.offset((page - 1) * size).limit(size)
        result = await self.db.execute(stmt)
        parent_replies = list(result.scalars().all())

        # 대댓글은 별도로 조회하여 반환 (비동기 세션에서는 relationship 직접 설정 불가)
        child_replies_dict = {}
        if parent_replies:
            parent_ids = [reply.reply_id for reply in parent_replies]
            child_stmt = select(Reply).where(
                Reply.parent_reply_id.in_(parent_ids),
                Reply.is_deleted == False  # 삭제되지 않은 대댓글만
            ).order_by(asc(Reply.created_at))
            child_result = await self.db.execute(child_stmt)
            child_replies = list(child_result.scalars().all())
            
            # 대댓글을 부모 댓글별로 그룹화
            for child in child_replies:
                if child.parent_reply_id not in child_replies_dict:
                    child_replies_dict[child.parent_reply_id] = []
                child_replies_dict[child.parent_reply_id].append(child)
            
            # 부모 댓글 객체에 대댓글 리스트를 속성으로 저장 (relationship과 충돌 방지)
            for parent_reply in parent_replies:
                # relationship이 아닌 일반 속성으로 할당하여 lazy loading 방지
                # relationship 이름(child_replies)과 충돌하지 않도록 다른 이름 사용
                object.__setattr__(parent_reply, '_nested_replies', child_replies_dict.get(parent_reply.reply_id, []))

        return parent_replies, total

    async def get_reply_by_id(self, reply_id: int) -> Optional[Reply]:
        """ID로 댓글 조회"""
        result = await self.db.execute(select(Reply).where(Reply.reply_id == reply_id))
        return result.scalar_one_or_none()

    async def create_reply(self, user_id: int, post_id: int, reply_data: ReplyCreate) -> Reply:
        """댓글 생성 (대댓글 지원)"""
        # parent_reply_id가 0이면 None으로 변환
        parent_reply_id = reply_data.parent_reply_id if reply_data.parent_reply_id and reply_data.parent_reply_id != 0 else None
        
        # 대댓글인 경우 부모 댓글이 같은 게시글에 속하는지 확인
        if parent_reply_id:
            parent_reply = await self.get_reply_by_id(parent_reply_id)
            if not parent_reply:
                raise ValueError("부모 댓글을 찾을 수 없습니다")
            if parent_reply.post_id != post_id:
                raise ValueError("부모 댓글이 해당 게시글에 속하지 않습니다")
        
        reply = Reply(
            user_id=user_id,
            post_id=post_id,
            content=reply_data.content,
            parent_reply_id=parent_reply_id
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
        
        # 삭제된 댓글은 수정 불가
        if reply.is_deleted:
            raise ValueError("삭제된 댓글은 수정할 수 없습니다")
        
        update_data = reply_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(reply, field, value)

        await self.db.commit()
        await self.db.refresh(reply)
        
        return reply
    
    async def delete_reply(self, reply_id: int) -> bool:
        """댓글 삭제 (대댓글이 있으면 삭제 표시만, 없으면 실제 삭제)"""
        reply = await self.get_reply_by_id(reply_id)
        if not reply:
            return False
        
        # 대댓글이 있는지 확인 (parent_reply_id가 이 댓글인 댓글들, 삭제되지 않은 것만)
        child_replies_stmt = select(Reply).where(
            Reply.parent_reply_id == reply_id,
            Reply.is_deleted == False
        )
        child_result = await self.db.execute(child_replies_stmt)
        child_replies = list(child_result.scalars().all())
        
        if child_replies:
            # 대댓글이 있으면 삭제 표시만 (실제 삭제하지 않음)
            reply.is_deleted = True
            reply.content = "삭제된 댓글입니다."
            await self.db.commit()
            await self.db.refresh(reply)
        else:
            # 대댓글이 없으면 실제 삭제
            await self.db.delete(reply)
            await self.db.commit()
            
            # 부모 댓글이 삭제 표시 상태이고, 남은 대댓글이 없으면 부모 댓글도 실제 삭제
            if reply.parent_reply_id:
                await self._check_and_delete_parent_if_empty(reply.parent_reply_id)
        
        return True
    
    async def _check_and_delete_parent_if_empty(self, parent_reply_id: int) -> None:
        """부모 댓글이 삭제 표시 상태이고 대댓글이 모두 삭제되었으면 실제 삭제"""
        parent_reply = await self.get_reply_by_id(parent_reply_id)
        if not parent_reply:
            return
        
        # 부모 댓글이 삭제 표시 상태인지 확인
        if not parent_reply.is_deleted:
            return
        
        # 남은 대댓글이 있는지 확인 (삭제되지 않은 것만)
        remaining_children_stmt = select(Reply).where(
            Reply.parent_reply_id == parent_reply_id,
            Reply.is_deleted == False
        )
        remaining_result = await self.db.execute(remaining_children_stmt)
        remaining_children = list(remaining_result.scalars().all())
        
        # 남은 대댓글이 없으면 부모 댓글도 실제 삭제
        if not remaining_children:
            await self.db.delete(parent_reply)
            await self.db.commit()
            
            # 재귀적으로 상위 부모 댓글도 확인
            if parent_reply.parent_reply_id:
                await self._check_and_delete_parent_if_empty(parent_reply.parent_reply_id)
    
    async def pin_post(self, post_id: int, is_pinned: bool) -> Optional[Post]:
        """게시글 고정/고정 해제"""
        post = await self.get_post_by_id(post_id)
        if not post:
            return None
        
        post.is_pinned = is_pinned
        await self.db.commit()
        await self.db.refresh(post)
        
        return post
    
    async def is_admin(self, user_id: int) -> bool:
        """사용자가 관리자인지 확인"""
        from app.models.user import User
        result = await self.db.execute(select(User).where(User.user_id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            return False
        return user.role == UserRole.ADMIN.value or user.role == "admin"
    
    async def toggle_post_like(self, post_id: int, user_id: int) -> Tuple[bool, bool]:
        """
        게시글 좋아요 토글
        Returns: (is_liked: bool, created: bool)
        - is_liked: 현재 좋아요 상태 (True: 좋아요 함, False: 좋아요 안 함)
        - created: 좋아요를 생성했는지 여부 (True: 생성, False: 삭제)
        """
        # 게시글 존재 확인
        post = await self.get_post_by_id(post_id)
        if not post:
            raise ValueError("게시글을 찾을 수 없습니다")
        
        # 기존 좋아요 확인
        existing_like_stmt = select(PostLike).where(
            PostLike.post_id == post_id,
            PostLike.user_id == user_id
        )
        existing_like_result = await self.db.execute(existing_like_stmt)
        existing_like = existing_like_result.scalar_one_or_none()
        
        if existing_like:
            # 좋아요 취소
            await self.db.delete(existing_like)
            await self.db.commit()
            return False, False
        else:
            # 좋아요 추가
            new_like = PostLike(
                post_id=post_id,
                user_id=user_id
            )
            self.db.add(new_like)
            await self.db.commit()
            await self.db.refresh(new_like)
            return True, True
    
    async def get_post_like_status(self, post_id: int, user_id: Optional[int]) -> bool:
        """사용자가 게시글에 좋아요를 눌렀는지 확인"""
        if not user_id:
            return False
        
        like_stmt = select(PostLike).where(
            PostLike.post_id == post_id,
            PostLike.user_id == user_id
        )
        like_result = await self.db.execute(like_stmt)
        like = like_result.scalar_one_or_none()
        
        return like is not None
    
    async def get_my_posts(
        self,
        user_id: int,
        category: Optional[str] = None,
        page: int = 1,
        size: int = 20
    ) -> Tuple[List[Post], int]:
        """내가 쓴 글 목록 조회"""
        stmt = select(Post).where(Post.user_id == user_id)
        
        if category:
            stmt = stmt.where(Post.category == category)
        
        # 생성일 내림차순 정렬
        stmt = stmt.order_by(desc(Post.created_at))
        
        # 전체 개수
        count_stmt = select(func.count()).select_from(stmt.alias())
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar() or 0
        
        # 페이징
        stmt = stmt.offset((page - 1) * size).limit(size)
        result = await self.db.execute(stmt)
        posts = list(result.scalars().all())
        
        # 각 게시글의 댓글 수와 좋아요 수 조회
        if posts:
            post_ids = [post.post_id for post in posts]
            
            # 댓글 수 조회
            reply_count_stmt = select(
                Reply.post_id,
                func.count(Reply.reply_id).label('reply_count')
            ).where(
                Reply.post_id.in_(post_ids)
            ).group_by(Reply.post_id)
            
            reply_count_result = await self.db.execute(reply_count_stmt)
            reply_counts = {row.post_id: row.reply_count for row in reply_count_result}
            
            # 좋아요 수 조회
            like_count_stmt = select(
                PostLike.post_id,
                func.count(PostLike.like_id).label('like_count')
            ).where(
                PostLike.post_id.in_(post_ids)
            ).group_by(PostLike.post_id)
            
            like_count_result = await self.db.execute(like_count_stmt)
            like_counts = {row.post_id: row.like_count for row in like_count_result}
            
            # 각 게시글에 댓글 수와 좋아요 수 할당
            for post in posts:
                object.__setattr__(post, 'reply_count', reply_counts.get(post.post_id, 0))
                object.__setattr__(post, 'like_count', like_counts.get(post.post_id, 0))
        
        return posts, total
    
    async def get_my_replies(
        self,
        user_id: int,
        page: int = 1,
        size: int = 20
    ) -> Tuple[List[Reply], int]:
        """내가 쓴 댓글 목록 조회"""
        stmt = select(Reply).where(Reply.user_id == user_id)
        
        # 생성일 내림차순 정렬
        stmt = stmt.order_by(desc(Reply.created_at))
        
        # 전체 개수
        count_stmt = select(func.count()).select_from(stmt.alias())
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar() or 0
        
        # 페이징
        stmt = stmt.offset((page - 1) * size).limit(size)
        result = await self.db.execute(stmt)
        replies = list(result.scalars().all())
        
        return replies, total
    
    async def search_posts(
        self,
        query: str,
        category: Optional[str] = None,
        page: int = 1,
        size: int = 20
    ) -> Tuple[List[Post], int]:
        """게시글 검색 (제목, 내용)"""
        # 제목 또는 내용에 검색어가 포함된 게시글 검색
        search_filter = or_(
            Post.title.ilike(f"%{query}%"),
            Post.content.ilike(f"%{query}%")
        )
        
        stmt = select(Post).where(search_filter)
        
        if category:
            stmt = stmt.where(Post.category == category)
        
        # 고정공지 우선, 그 다음 생성일 내림차순
        stmt = stmt.order_by(desc(Post.is_pinned), desc(Post.created_at))
        
        # 전체 개수
        count_stmt = select(func.count()).select_from(stmt.alias())
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar() or 0
        
        # 페이징
        stmt = stmt.offset((page - 1) * size).limit(size)
        result = await self.db.execute(stmt)
        posts = list(result.scalars().all())
        
        # 각 게시글의 댓글 수와 좋아요 수 조회
        if posts:
            post_ids = [post.post_id for post in posts]
            
            # 댓글 수 조회
            reply_count_stmt = select(
                Reply.post_id,
                func.count(Reply.reply_id).label('reply_count')
            ).where(
                Reply.post_id.in_(post_ids)
            ).group_by(Reply.post_id)
            
            reply_count_result = await self.db.execute(reply_count_stmt)
            reply_counts = {row.post_id: row.reply_count for row in reply_count_result}
            
            # 좋아요 수 조회
            like_count_stmt = select(
                PostLike.post_id,
                func.count(PostLike.like_id).label('like_count')
            ).where(
                PostLike.post_id.in_(post_ids)
            ).group_by(PostLike.post_id)
            
            like_count_result = await self.db.execute(like_count_stmt)
            like_counts = {row.post_id: row.like_count for row in like_count_result}
            
            # 각 게시글에 댓글 수와 좋아요 수 할당
            for post in posts:
                object.__setattr__(post, 'reply_count', reply_counts.get(post.post_id, 0))
                object.__setattr__(post, 'like_count', like_counts.get(post.post_id, 0))
        
        return posts, total
