"""
데이터베이스 연결 및 세션 관리
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.pool import NullPool
from typing import AsyncGenerator

from app.core.config import settings

# 데이터베이스 엔진 생성 (비동기)
engine = create_async_engine(
    settings.DATABASE_URL,
    poolclass=NullPool,
    echo=settings.DEBUG
)

# 세션 팩토리 생성 (비동기)
SessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

# 베이스 클래스
Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """데이터베이스 세션 의존성 (비동기)"""
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """데이터베이스 초기화 (비동기)"""
    async with engine.begin() as conn:
        # 모든 테이블 생성
        await conn.run_sync(Base.metadata.create_all)
