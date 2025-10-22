"""
사용자 관련 API 엔드포인트
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.core.security import get_current_user_id, oauth2_scheme
from app.schemas.user import (
    UserResponse, UserUpdate, UserPasswordChange, 
    UserLanguageChange, UserJobChange, UserThemeChange, UserStatusResponse
)
from app.schemas.common import BaseResponse
from app.services.user_service import UserService

router = APIRouter()


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """현재 사용자 정보 가져오기"""
    user_id = get_current_user_id(token)
    user_service = UserService(db)
    user = user_service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="사용자를 찾을 수 없습니다"
        )
    return user


@router.get("/", response_model=UserResponse)
async def get_current_user_info(
    current_user = Depends(get_current_user)
):
    """내 정보 조회"""
    return current_user


@router.put("/", response_model=BaseResponse)
async def update_user_info(
    user_update: UserUpdate,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """사용자 정보 전체 수정"""
    user_service = UserService(db)
    user_service.update_user(current_user.user_id, user_update)
    
    return BaseResponse(
        success=True,
        message="사용자 정보가 수정되었습니다"
    )


@router.patch("/password", response_model=BaseResponse)
async def change_password(
    password_change: UserPasswordChange,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """비밀번호 변경"""
    user_service = UserService(db)
    
    # 현재 비밀번호 확인
    if not user_service.verify_user_password(current_user.user_id, password_change.current_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="현재 비밀번호가 올바르지 않습니다"
        )
    
    # 새 비밀번호로 변경
    user_service.update_user_password(current_user.user_id, password_change.new_password)
    
    return BaseResponse(
        success=True,
        message="비밀번호가 변경되었습니다"
    )


@router.patch("/language", response_model=BaseResponse)
async def change_language(
    language_change: UserLanguageChange,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """모국어 변경"""
    user_service = UserService(db)
    user_service.update_user_language(current_user.user_id, language_change.level_id)
    
    return BaseResponse(
        success=True,
        message="모국어가 변경되었습니다"
    )


@router.patch("/job", response_model=BaseResponse)
async def change_job(
    job_change: UserJobChange,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """직무 변경"""
    user_service = UserService(db)
    user_service.update_user_job(current_user.user_id, job_change.job_id)
    
    return BaseResponse(
        success=True,
        message="직무가 변경되었습니다"
    )


@router.patch("/theme", response_model=BaseResponse)
async def change_theme(
    theme_change: UserThemeChange,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """테마 변경"""
    user_service = UserService(db)
    user_service.update_user_theme(current_user.user_id, theme_change.theme)
    
    return BaseResponse(
        success=True,
        message="테마가 변경되었습니다"
    )


@router.get("/{user_id}/status", response_model=UserStatusResponse)
async def get_user_status(
    user_id: int,
    db: Session = Depends(get_db)
):
    """사용자 학습 상태(통계) 조회"""
    user_service = UserService(db)
    user_status = user_service.get_user_status(user_id)
    
    if not user_status:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="사용자 상태 정보를 찾을 수 없습니다"
        )
    
    return user_status
