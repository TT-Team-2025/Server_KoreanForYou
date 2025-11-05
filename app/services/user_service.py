"""
사용자 관련 서비스
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List
from datetime import datetime, timezone

from app.models.user import User, Job, UserLevel, UserStatus
from app.schemas.user import UserCreate, UserUpdate
from app.core.security import get_password_hash, verify_password


class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """ID로 사용자 조회"""
        result = await self.db.execute(select(User).where(User.user_id == user_id))
        return result.scalar_one_or_none()

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """이메일로 사용자 조회"""
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def create_user(self, user_data: UserCreate) -> User:
        """사용자 생성"""
        hashed_password = get_password_hash(user_data.password)
        
        user = User(
            email=user_data.email,
            password=hashed_password,
            nickname=user_data.nickname,
            nationality=user_data.nationality,
            job_id=user_data.job_id,
            level_id=user_data.level_id,
            description=user_data.description
        )
        
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)

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
        await self.db.commit()
        
        return user
    
    async def update_user(self, user_id: int, user_update: UserUpdate) -> Optional[User]:
        """사용자 정보 수정"""
        user = await self.get_user_by_id(user_id)
        if not user:
            return None
        
        update_data = user_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(user, field, value)

        user.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(user)
        
        # 업데이트 된 데이터만 반환
        return update_data
    
    async def update_user_password(self, user_id: int, new_password: str) -> bool:
        """사용자 비밀번호 변경"""
        user = await self.get_user_by_id(user_id)
        if not user:
            return False
        
        user.password = get_password_hash(new_password)
        user.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        
        return True
    
    async def update_user_language(self, user_id: int, nationality: str) -> str:
        """사용자 모국어 변경"""
        user = await self.get_user_by_id(user_id)
        if not user:
            return False
        
        user.nationality = nationality
        user.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        
        return nationality
    
    async def update_user_job(self, user_id: int, job_id: int) -> Optional[int]:
        """사용자 직무 변경"""
        user = await self.get_user_by_id(user_id)
        if not user:
            return False
        
        user.job_id = job_id
        user.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        
        return job_id
    
    async def authenticate_user(self, email: str, password: str) -> Optional[User]:
        """사용자 인증"""
        user = await self.get_user_by_email(email)
        if not user:
            return None
        
        if not verify_password(password, user.password):
            return None
        
        return user
    
    async def verify_user_password(self, user_id: int, password: str) -> bool:
        """사용자 비밀번호 확인"""
        user = await self.get_user_by_id(user_id)
        if not user:
            return False
        
        return verify_password(password, user.password)
    
    async def get_user_status(self, user_id: int) -> Optional[UserStatus]:
        """사용자 상태 조회"""
        result = await self.db.execute(select(UserStatus).where(UserStatus.user_id == user_id))
        return result.scalar_one_or_none()

    async def get_job_by_id(self, job_id: int) -> Optional[Job]:
        """직무 조회"""
        result = await self.db.execute(select(Job).where(Job.job_id == job_id))
        return result.scalar_one_or_none()

    async def get_level_by_id(self, level_id: int) -> Optional[UserLevel]:
        """레벨 조회"""
        result = await self.db.execute(select(UserLevel).where(UserLevel.level_id == level_id))
        return result.scalar_one_or_none()

    async def get_all_jobs(self) -> List[Job]:
        """모든 직무 조회"""
        result = await self.db.execute(select(Job))
        return list(result.scalars().all())

    async def get_all_levels(self) -> List[UserLevel]:
        """모든 레벨 조회"""
        result = await self.db.execute(select(UserLevel))
        return list(result.scalars().all())

    async def create_job(self, job_name: str, description: Optional[str] = None) -> Job:
        """직무 생성"""
        job = Job(
            job_name=job_name,
            description=description
        )
        self.db.add(job)
        await self.db.commit()
        await self.db.refresh(job)

        return job

    async def create_level(self, level_name: str, description: Optional[str] = None) -> UserLevel:
        """레벨 생성"""
        level = UserLevel(
            level_name=level_name,
            description=description
        )
        self.db.add(level)
        await self.db.commit()
        await self.db.refresh(level)

        return level