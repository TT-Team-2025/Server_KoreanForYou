"""
커뮤니티 관련 API 엔드포인트
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.database import get_db
from app.core.security import get_current_user_id, oauth2_scheme
from app.schemas.community import (
    PostResponse, PostDetailResponse, PostCreate, PostUpdate, PostListResponse,
    ReplyResponse, ReplyCreate, ReplyUpdate, ReplyListResponse
)
from app.schemas.common import BaseResponse
from app.services.community_service import CommunityService

router = APIRouter()


@router.get("/", response_model=PostListResponse)
async def get_posts(
    category: Optional[str] = Query(None, description="카테고리"),
    sort: Optional[str] = Query("created_at", description="정렬 기준"),
    page: int = Query(1, ge=1, description="페이지 번호"),
    size: int = Query(20, ge=1, le=100, description="페이지 크기"),
    db: AsyncSession = Depends(get_db)
):
    """게시글 목록 조회"""
    community_service = CommunityService(db)
    posts, total = await community_service.get_posts(
        category=category,
        sort=sort,
        page=page,
        size=size
    )

    return PostListResponse(
        posts=posts,
        total=total,
        page=page,
        size=size
    )


@router.get("/search", response_model=PostListResponse)
async def search_posts(
    q: str = Query(..., description="검색어"),
    category: Optional[str] = Query(None, description="카테고리"),
    page: int = Query(1, ge=1, description="페이지 번호"),
    size: int = Query(20, ge=1, le=100, description="페이지 크기"),
    db: AsyncSession = Depends(get_db)
):
    """게시글 검색 (제목, 내용)"""
    if not q or not q.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="검색어를 입력해주세요"
        )
    
    community_service = CommunityService(db)
    
    posts, total = await community_service.search_posts(
        query=q.strip(),
        category=category,
        page=page,
        size=size
    )
    
    return PostListResponse(
        posts=posts,
        total=total,
        page=page,
        size=size
    )


@router.get("/my-posts", response_model=PostListResponse)
async def get_my_posts(
    category: Optional[str] = Query(None, description="카테고리"),
    page: int = Query(1, ge=1, description="페이지 번호"),
    size: int = Query(20, ge=1, le=100, description="페이지 크기"),
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """내가 쓴 글 목록 조회"""
    user_id = get_current_user_id(token)
    community_service = CommunityService(db)
    
    posts, total = await community_service.get_my_posts(
        user_id=user_id,
        category=category,
        page=page,
        size=size
    )
    
    return PostListResponse(
        posts=posts,
        total=total,
        page=page,
        size=size
    )


@router.get("/{post_id}", response_model=PostDetailResponse)
async def get_post(
    post_id: int,
    include_replies: bool = Query(True, description="댓글 포함 여부"),
    db: AsyncSession = Depends(get_db)
):
    """게시글 상세 조회"""
    community_service = CommunityService(db)
    post = await community_service.get_post_by_id(post_id)

    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="게시글을 찾을 수 없습니다"
        )

    # lazy loading 방지: increment_view_count 호출 전에 모든 필드를 변수에 저장
    # increment_view_count가 세션을 변경할 수 있으므로 미리 저장
    post_id_val = int(post.post_id)
    user_id_val = int(post.user_id)
    title_val = str(post.title)
    content_val = str(post.content)
    category_val = post.category.value if hasattr(post.category, 'value') else str(post.category)
    is_pinned_val = bool(post.is_pinned)
    view_count_val = int(post.view_count)
    reply_count_val = int(getattr(post, 'reply_count', 0))
    like_count_val = int(getattr(post, 'like_count', 0))
    created_at_val = post.created_at
    updated_at_val = post.updated_at

    # 조회수 증가 (이후 post 객체는 사용하지 않음)
    await community_service.increment_view_count(post_id)
    
    # 댓글 포함 여부에 따라 댓글 조회
    if include_replies:
        replies, _ = await community_service.get_post_replies(post_id, page=1, size=1000)
        
        # Reply 모델을 ReplyResponse로 변환 (대댓글 포함)
        from app.schemas.community import ReplyResponse
        reply_responses = []
        for reply in replies:
            # 대댓글 가져오기 (_nested_replies 속성에서)
            child_replies = getattr(reply, '_nested_replies', [])
            child_responses = [
                ReplyResponse(
                    reply_id=child.reply_id,
                    post_id=child.post_id,
                    user_id=child.user_id,
                    parent_reply_id=child.parent_reply_id,
                    content=child.content,
                    is_deleted=child.is_deleted,
                    created_at=child.created_at,
                    updated_at=child.updated_at,
                    child_replies=[]  # 대댓글의 대댓글은 없음
                ) for child in child_replies
            ]
            
            reply_response = ReplyResponse(
                reply_id=reply.reply_id,
                post_id=reply.post_id,
                user_id=reply.user_id,
                parent_reply_id=reply.parent_reply_id,
                content=reply.content,
                is_deleted=reply.is_deleted,
                created_at=reply.created_at,
                updated_at=reply.updated_at,
                child_replies=child_responses
            )
            reply_responses.append(reply_response)
        
        # PostDetailResponse로 변환 (이미 저장된 변수 사용)
        from app.schemas.community import PostDetailResponse
        post_detail = PostDetailResponse(
            post_id=post_id_val,
            user_id=user_id_val,
            title=title_val,
            content=content_val,
            category=category_val,
            is_pinned=is_pinned_val,
            view_count=view_count_val,
            reply_count=reply_count_val,
            like_count=like_count_val,
            created_at=created_at_val,
            updated_at=updated_at_val,
            replies=reply_responses
        )
        return post_detail
    else:
        # 댓글 없이 반환 (이미 저장된 변수 사용)
        from app.schemas.community import PostDetailResponse
        post_detail = PostDetailResponse(
            post_id=post_id_val,
            user_id=user_id_val,
            title=title_val,
            content=content_val,
            category=category_val,
            is_pinned=is_pinned_val,
            view_count=view_count_val,
            reply_count=reply_count_val,
            like_count=like_count_val,
            created_at=created_at_val,
            updated_at=updated_at_val,
            replies=None
        )
        return post_detail


@router.post("/", response_model=BaseResponse)
async def create_post(
    post_data: PostCreate,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """게시글 작성"""
    user_id = get_current_user_id(token)
    community_service = CommunityService(db)

    post = await community_service.create_post(user_id, post_data)

    return BaseResponse(
        success=True,
        message="게시글이 작성되었습니다",
        data={"post_id": post.post_id}
    )


@router.put("/{post_id}", response_model=BaseResponse)
async def update_post(
    post_id: int,
    post_update: PostUpdate,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """게시글 수정"""
    user_id = get_current_user_id(token)
    community_service = CommunityService(db)

    # 게시글 소유자 확인
    post = await community_service.get_post_by_id(post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="게시글을 찾을 수 없습니다"
        )

    if post.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="게시글을 수정할 권한이 없습니다"
        )

    await community_service.update_post(post_id, post_update)

    return BaseResponse(
        success=True,
        message="게시글이 수정되었습니다"
    )


@router.delete("/{post_id}", response_model=BaseResponse)
async def delete_post(
    post_id: int,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """게시글 삭제"""
    user_id = get_current_user_id(token)
    community_service = CommunityService(db)

    # 게시글 소유자 확인
    post = await community_service.get_post_by_id(post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="게시글을 찾을 수 없습니다"
        )

    if post.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="게시글을 삭제할 권한이 없습니다"
        )

    await community_service.delete_post(post_id)

    return BaseResponse(
        success=True,
        message="게시글이 삭제되었습니다"
    )


@router.get("/{post_id}/replies", response_model=ReplyListResponse)
async def get_post_replies(
    post_id: int,
    page: int = Query(1, ge=1, description="페이지 번호"),
    size: int = Query(20, ge=1, le=100, description="페이지 크기"),
    db: AsyncSession = Depends(get_db)
):
    """댓글 목록 조회"""
    community_service = CommunityService(db)

    if not await community_service.get_post_by_id(post_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="게시글을 찾을 수 없습니다"
        )

    replies, total = await community_service.get_post_replies(
        post_id=post_id,
        page=page,
        size=size
    )
    
    # Reply 모델을 ReplyResponse로 변환 (대댓글 포함)
    from app.schemas.community import ReplyResponse
    reply_responses = []
    for reply in replies:
        # 대댓글 가져오기 (_nested_replies 속성에서)
        child_replies = getattr(reply, '_nested_replies', [])
        child_responses = [
            ReplyResponse(
                reply_id=child.reply_id,
                post_id=child.post_id,
                user_id=child.user_id,
                parent_reply_id=child.parent_reply_id,
                content=child.content,
                created_at=child.created_at,
                updated_at=child.updated_at,
                child_replies=[]  # 대댓글의 대댓글은 없음
            ) for child in child_replies
        ]
        
        reply_response = ReplyResponse(
            reply_id=reply.reply_id,
            post_id=reply.post_id,
            user_id=reply.user_id,
            parent_reply_id=reply.parent_reply_id,
            content=reply.content,
            created_at=reply.created_at,
            updated_at=reply.updated_at,
            child_replies=child_responses
        )
        reply_responses.append(reply_response)

    return ReplyListResponse(
        replies=reply_responses,
        total=total,
        page=page,
        size=size
    )


@router.post("/{post_id}/replies", response_model=BaseResponse)
async def create_reply(
    post_id: int,
    reply_data: ReplyCreate,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """댓글 작성"""
    user_id = get_current_user_id(token)
    community_service = CommunityService(db)

    if not await community_service.get_post_by_id(post_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="게시글을 찾을 수 없습니다"
        )

    try:
        reply = await community_service.create_reply(user_id, post_id, reply_data)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    return BaseResponse(
        success=True,
        message="댓글이 작성되었습니다",
        data={"reply_id": reply.reply_id}
    )


@router.put("/replies/{reply_id}", response_model=BaseResponse)
async def update_reply(
    reply_id: int,
    reply_update: ReplyUpdate,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """댓글 수정"""
    user_id = get_current_user_id(token)
    community_service = CommunityService(db)

    # 댓글 소유자 확인
    reply = await community_service.get_reply_by_id(reply_id)
    if not reply:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="댓글을 찾을 수 없습니다"
        )

    if reply.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="댓글을 수정할 권한이 없습니다"
        )

    await community_service.update_reply(reply_id, reply_update)

    return BaseResponse(
        success=True,
        message="댓글이 수정되었습니다"
    )


@router.delete("/replies/{reply_id}", response_model=BaseResponse)
async def delete_reply(
    reply_id: int,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """댓글 삭제"""
    user_id = get_current_user_id(token)
    community_service = CommunityService(db)

    # 댓글 소유자 확인
    reply = await community_service.get_reply_by_id(reply_id)
    if not reply:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="댓글을 찾을 수 없습니다"
        )

    if reply.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="댓글을 삭제할 권한이 없습니다"
        )

    await community_service.delete_reply(reply_id)

    return BaseResponse(
        success=True,
        message="댓글이 삭제되었습니다"
    )


@router.get("/replies/my-replies", response_model=ReplyListResponse)
async def get_my_replies(
    page: int = Query(1, ge=1, description="페이지 번호"),
    size: int = Query(20, ge=1, le=100, description="페이지 크기"),
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """내가 쓴 댓글 목록 조회"""
    user_id = get_current_user_id(token)
    community_service = CommunityService(db)
    
    replies, total = await community_service.get_my_replies(
        user_id=user_id,
        page=page,
        size=size
    )
    
    # Reply 모델을 ReplyResponse로 변환
    from app.schemas.community import ReplyResponse
    reply_responses = []
    for reply in replies:
        reply_response = ReplyResponse(
            reply_id=reply.reply_id,
            post_id=reply.post_id,
            user_id=reply.user_id,
            parent_reply_id=reply.parent_reply_id,
            content=reply.content,
            is_deleted=reply.is_deleted,
            created_at=reply.created_at,
            updated_at=reply.updated_at,
            child_replies=[]  # 목록 조회에서는 대댓글 미포함
        )
        reply_responses.append(reply_response)
    
    return ReplyListResponse(
        replies=reply_responses,
        total=total,
        page=page,
        size=size
    )


#게시글 고정
@router.put("/{post_id}/pin", response_model=BaseResponse)
async def pin_post(
    post_id: int,
    is_pinned: bool = Query(..., description="고정 여부"),
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """게시글 고정/고정 해제 (관리자만 가능)"""
    user_id = get_current_user_id(token)
    community_service = CommunityService(db)

    # 관리자 권한 확인
    if not await community_service.is_admin(user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자만 게시글을 고정할 수 있습니다"
        )

    # 게시글 존재 확인
    post = await community_service.get_post_by_id(post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="게시글을 찾을 수 없습니다"
        )

    await community_service.pin_post(post_id, is_pinned)

    return BaseResponse(
        success=True,
        message="고정공지가 설정되었습니다" if is_pinned else "고정공지가 해제되었습니다"
    )


@router.post("/{post_id}/like", response_model=BaseResponse)
async def toggle_post_like(
    post_id: int,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """게시글 좋아요 토글"""
    user_id = get_current_user_id(token)
    community_service = CommunityService(db)
    
    try:
        is_liked, created = await community_service.toggle_post_like(post_id, user_id)
        
        if created:
            message = "좋아요를 추가했습니다"
        else:
            message = "좋아요를 취소했습니다"
        
        return BaseResponse(
            success=True,
            message=message,
            data={"is_liked": is_liked}
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


