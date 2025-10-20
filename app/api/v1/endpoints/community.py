"""
커뮤니티 관련 API 엔드포인트
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.core.security import get_current_user_id, oauth2_scheme
from app.schemas.community import (
    PostResponse, PostCreate, PostUpdate, PostListResponse,
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
    db: Session = Depends(get_db)
):
    """게시글 목록 조회"""
    community_service = CommunityService(db)
    posts, total = community_service.get_posts(
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


@router.get("/{post_id}", response_model=PostResponse)
async def get_post(
    post_id: int,
    db: Session = Depends(get_db)
):
    """게시글 상세 조회"""
    community_service = CommunityService(db)
    post = community_service.get_post_by_id(post_id)
    
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="게시글을 찾을 수 없습니다"
        )
    
    # 조회수 증가
    community_service.increment_view_count(post_id)
    
    return post


@router.post("/", response_model=BaseResponse)
async def create_post(
    post_data: PostCreate,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """게시글 작성"""
    user_id = get_current_user_id(token)
    community_service = CommunityService(db)
    
    post = community_service.create_post(user_id, post_data)
    
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
    db: Session = Depends(get_db)
):
    """게시글 수정"""
    user_id = get_current_user_id(token)
    community_service = CommunityService(db)
    
    # 게시글 소유자 확인
    post = community_service.get_post_by_id(post_id)
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
    
    community_service.update_post(post_id, post_update)
    
    return BaseResponse(
        success=True,
        message="게시글이 수정되었습니다"
    )


@router.delete("/{post_id}", response_model=BaseResponse)
async def delete_post(
    post_id: int,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """게시글 삭제"""
    user_id = get_current_user_id(token)
    community_service = CommunityService(db)
    
    # 게시글 소유자 확인
    post = community_service.get_post_by_id(post_id)
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
    
    community_service.delete_post(post_id)
    
    return BaseResponse(
        success=True,
        message="게시글이 삭제되었습니다"
    )


@router.get("/{post_id}/replies", response_model=ReplyListResponse)
async def get_post_replies(
    post_id: int,
    page: int = Query(1, ge=1, description="페이지 번호"),
    size: int = Query(20, ge=1, le=100, description="페이지 크기"),
    db: Session = Depends(get_db)
):
    """댓글 목록 조회"""
    community_service = CommunityService(db)
    
    if not community_service.get_post_by_id(post_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="게시글을 찾을 수 없습니다"
        )
    
    replies, total = community_service.get_post_replies(
        post_id=post_id,
        page=page,
        size=size
    )
    
    return ReplyListResponse(
        replies=replies,
        total=total,
        page=page,
        size=size
    )


@router.post("/{post_id}/replies", response_model=BaseResponse)
async def create_reply(
    post_id: int,
    reply_data: ReplyCreate,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """댓글 작성"""
    user_id = get_current_user_id(token)
    community_service = CommunityService(db)
    
    if not community_service.get_post_by_id(post_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="게시글을 찾을 수 없습니다"
        )
    
    reply = community_service.create_reply(user_id, post_id, reply_data)
    
    return BaseResponse(
        success=True,
        message="댓글이 작성되었습니다",
        data={"reply_id": reply.reply_id}
    )


@router.delete("/replies/{reply_id}", response_model=BaseResponse)
async def delete_reply(
    reply_id: int,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """댓글 삭제"""
    user_id = get_current_user_id(token)
    community_service = CommunityService(db)
    
    # 댓글 소유자 확인
    reply = community_service.get_reply_by_id(reply_id)
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
    
    community_service.delete_reply(reply_id)
    
    return BaseResponse(
        success=True,
        message="댓글이 삭제되었습니다"
    )
