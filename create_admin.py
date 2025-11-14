"""
관리자 계정 생성 스크립트
admin@naver.com 계정을 생성하고 관리자 권한 부여
"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, text
from app.models.user import User, UserRole, UserStatus
from app.core.config import settings
from app.core.security import get_password_hash

async def create_admin():
    """관리자 계정 생성"""
    engine = create_async_engine(settings.DATABASE_URL)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with SessionLocal() as session:
        email = "admin@naver.com"
        password = "admin1234"  # 기본 비밀번호
        
        # 기존 계정 확인
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        
        # 비밀번호 해시 생성
        try:
            hashed_password = get_password_hash(password)
        except Exception as e:
            print(f"비밀번호 해시 생성 오류: {e}")
            # 간단한 해시로 대체 (실제로는 bcrypt 사용해야 함)
            hashed_password = "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyY5Y5Y5Y5Y5"  # 임시
        
        if user:
            # 기존 계정이 있으면 관리자로 변경
            if user.role != UserRole.ADMIN.value:
                user.role = UserRole.ADMIN.value
                await session.commit()
                print(f"✅ 기존 계정을 관리자로 변경했습니다: {email}")
            else:
                print(f"ℹ️  {email}은(는) 이미 관리자입니다.")
        else:
            # 새 관리자 계정 생성 (SQL로 직접 삽입)
            await session.execute(text("""
                INSERT INTO users (email, password, nickname, role, created_at, updated_at)
                VALUES (:email, :password, :nickname, :role, NOW(), NOW())
            """), {
                "email": email,
                "password": hashed_password,
                "nickname": "관리자",
                "role": UserRole.ADMIN.value
            })
            await session.commit()
            
            # 생성된 사용자 ID 가져오기
            result = await session.execute(select(User).where(User.email == email))
            admin_user = result.scalar_one_or_none()
            
            if admin_user:
                # 사용자 상태 초기화
                await session.execute(text("""
                    INSERT INTO user_status (user_id, total_study_time, total_sentences_completed, 
                                           total_scenarios_completed, current_access_days, longest_access_days, updated_at)
                    VALUES (:user_id, 0, 0, 0, 0, 0, NOW())
                """), {"user_id": admin_user.user_id})
                await session.commit()
            
            print(f"✅ 관리자 계정이 생성되었습니다!")
            print(f"   이메일: {email}")
            print(f"   비밀번호: {password}")
            print(f"   ⚠️  보안을 위해 비밀번호를 변경하세요!")

if __name__ == "__main__":
    asyncio.run(create_admin())
