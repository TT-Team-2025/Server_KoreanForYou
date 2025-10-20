"""
사용자 관련 서비스
"""
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime

from app.models.user import User, Job, UserLevel, UserStatus
from app.schemas.user import UserCreate, UserUpdate, UserPasswordChange, UserLanguageChange, UserJobChange
from app.core.security import get_password_hash, verify_password


class UserService:
    def __init__(self, db: Session):
        self.db = db
    
    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """ID로 사용자 조회"""
        return self.db.query(User).filter(User.user_id == user_id).first()
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """이메일로 사용자 조회"""
        return self.db.query(User).filter(User.email == email).first()
    
    def create_user(self, user_data: UserCreate) -> User:
        """사용자 생성"""
        hashed_password = get_password_hash(user_data.password)
        
        user = User(
            email=user_data.email,
            password=hashed_password,
            nickname=user_data.nickname,
            nationality=user_data.nationality,
            job_id=user_data.job_id,
            level_id=user_data.level_id
        )
        
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        
        # 사용자 상태 초기화
        user_status = UserStatus(
            user_id=user.user_id,
            total_study_time=0,
            total_sentences_completed=0,
            total_scenarios_completed=0,
            current_access_days=0,
            longest_access_days=0
        )
        self.db.add(user_status)
        self.db.commit()
        
        return user
    
    def update_user(self, user_id: int, user_update: UserUpdate) -> Optional[User]:
        """사용자 정보 수정"""
        user = self.get_user_by_id(user_id)
        if not user:
            return None
        
        update_data = user_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(user, field, value)
        
        user.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(user)
        
        return user
    
    def update_user_password(self, user_id: int, new_password: str) -> bool:
        """사용자 비밀번호 변경"""
        user = self.get_user_by_id(user_id)
        if not user:
            return False
        
        user.password = get_password_hash(new_password)
        user.updated_at = datetime.utcnow()
        self.db.commit()
        
        return True
    
    def update_user_language(self, user_id: int, level_id: int) -> bool:
        """사용자 모국어 변경"""
        user = self.get_user_by_id(user_id)
        if not user:
            return False
        
        user.level_id = level_id
        user.updated_at = datetime.utcnow()
        self.db.commit()
        
        return True
    
    def update_user_job(self, user_id: int, job_id: int) -> bool:
        """사용자 직무 변경"""
        user = self.get_user_by_id(user_id)
        if not user:
            return False
        
        user.job_id = job_id
        user.updated_at = datetime.utcnow()
        self.db.commit()
        
        return True
    
    def authenticate_user(self, email: str, password: str) -> Optional[User]:
        """사용자 인증"""
        user = self.get_user_by_email(email)
        if not user:
            return None
        
        if not verify_password(password, user.password):
            return None
        
        return user
    
    def verify_user_password(self, user_id: int, password: str) -> bool:
        """사용자 비밀번호 확인"""
        user = self.get_user_by_id(user_id)
        if not user:
            return False
        
        return verify_password(password, user.password)
    
    def get_user_status(self, user_id: int) -> Optional[UserStatus]:
        """사용자 상태 조회"""
        return self.db.query(UserStatus).filter(UserStatus.user_id == user_id).first()
    
    def get_job_by_id(self, job_id: int) -> Optional[Job]:
        """직무 조회"""
        return self.db.query(Job).filter(Job.job_id == job_id).first()
    
    def get_level_by_id(self, level_id: int) -> Optional[UserLevel]:
        """레벨 조회"""
        return self.db.query(UserLevel).filter(UserLevel.level_id == level_id).first()
    
    def get_all_jobs(self) -> List[Job]:
        """모든 직무 조회"""
        return self.db.query(Job).all()
    
    def get_all_levels(self) -> List[UserLevel]:
        """모든 레벨 조회"""
        return self.db.query(UserLevel).all()
