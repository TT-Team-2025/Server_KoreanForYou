"""
비동기 기반 Alembic 마이그레이션 실행 및 생성 스크립트
"""
import sys
import os
import asyncio

# 프로젝트 루트 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 환경 변수 설정
from app.core.config import settings
if not os.environ.get('DATABASE_URL'):
    os.environ['DATABASE_URL'] = settings.DATABASE_URL

from alembic.config import Config
from alembic import command
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
from app.core.database import Base


async def create_migration_async(message: str = None):
    """새 마이그레이션 파일 생성 (autogenerate) - 비동기"""
    cfg = Config()
    cfg.set_main_option("script_location", "alembic")
    cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
    
    # 모든 모델 import (autogenerate가 변경사항을 감지하도록)
    import app.models  # noqa
    
    msg = message or "auto migration"
    print(f"Creating migration: {msg}")
    try:
        command.revision(cfg, autogenerate=True, message=msg)
        print("✓ Migration file created successfully!")
    except Exception as e:
        print(f"✗ Failed to create migration: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


async def upgrade_migration_async(revision: str = "head"):
    """마이그레이션 적용 - 비동기"""
    from alembic import context
    from alembic.script import ScriptDirectory
    from alembic.runtime.migration import MigrationContext
    
    cfg = Config()
    cfg.set_main_option("script_location", "alembic")
    cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
    
    # 비동기 엔진 생성
    async_engine = create_async_engine(
        settings.DATABASE_URL,
        poolclass=NullPool,
        echo=False
    )
    
    print(f"Applying migrations up to: {revision}")
    
    try:
        # Alembic 스크립트 디렉토리 로드
        script = ScriptDirectory.from_config(cfg)
        
        # 현재 리비전 확인
        async with async_engine.begin() as conn:
            def get_current_revision(connection):
                context = MigrationContext.configure(connection)
                return context.get_current_revision()
            
            current_rev = await conn.run_sync(get_current_revision)
            print(f"Current revision: {current_rev or 'None'}")
        
        # 마이그레이션 업그레이드 실행
        # Alembic command는 동기 방식이므로, 비동기 엔진을 동기 래퍼로 변환
        from sqlalchemy.pool import StaticPool
        from sqlalchemy import create_engine
        
        # 동기 URL로 변환 (비동기 URL에서 asyncpg를 psycopg2로 변환)
        sync_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
        
        sync_engine = create_engine(
            sync_url,
            poolclass=StaticPool,
            echo=False
        )
        
        # 동기 엔진으로 마이그레이션 실행
        with sync_engine.connect() as connection:
            cfg.attributes['connection'] = connection
            command.upgrade(cfg, revision)
        
        sync_engine.dispose()
        print("✓ Migration completed successfully!")
        
    except Exception as e:
        print(f"✗ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        await async_engine.dispose()


async def downgrade_migration_async(revision: str = "-1"):
    """마이그레이션 롤백 - 비동기"""
    cfg = Config()
    cfg.set_main_option("script_location", "alembic")
    cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
    
    # 동기 URL로 변환
    sync_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    
    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool
    
    sync_engine = create_engine(
        sync_url,
        poolclass=StaticPool,
        echo=False
    )
    
    print(f"Downgrading to: {revision}")
    try:
        with sync_engine.connect() as connection:
            cfg.attributes['connection'] = connection
            command.downgrade(cfg, revision)
        print("✓ Downgrade completed successfully!")
    except Exception as e:
        print(f"✗ Downgrade failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        sync_engine.dispose()


async def show_current_revision_async():
    """현재 마이그레이션 리비전 확인 - 비동기"""
    from alembic.runtime.migration import MigrationContext
    from sqlalchemy import text
    
    async_engine = create_async_engine(
        settings.DATABASE_URL,
        poolclass=NullPool,
        echo=False
    )
    
    try:
        async with async_engine.begin() as conn:
            # alembic_version 테이블 확인
            result = await conn.execute(
                text("SELECT version_num FROM alembic_version LIMIT 1")
            )
            row = result.fetchone()
            if row:
                print(f"Current revision: {row[0]}")
            else:
                print("No migrations applied yet")
    except Exception as e:
        if "alembic_version" in str(e):
            print("No migrations applied yet (alembic_version table does not exist)")
        else:
            print(f"Error checking revision: {e}")
    finally:
        await async_engine.dispose()


async def show_history_async():
    """마이그레이션 히스토리 확인 - 비동기"""
    cfg = Config()
    cfg.set_main_option("script_location", "alembic")
    
    from alembic.script import ScriptDirectory
    
    script = ScriptDirectory.from_config(cfg)
    
    print("Migration history:")
    for revision in script.walk_revisions():
        print(f"  {revision.revision}: {revision.doc}")


def main():
    """메인 함수"""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python migrate_async.py create [message]  - Create new migration (autogenerate)")
        print("  python migrate_async.py upgrade [revision] - Apply migrations (default: head)")
        print("  python migrate_async.py downgrade [revision] - Rollback migrations (default: -1)")
        print("  python migrate_async.py current - Show current revision")
        print("  python migrate_async.py history - Show migration history")
        sys.exit(1)
    
    action = sys.argv[1]
    
    if action == "create":
        message = sys.argv[2] if len(sys.argv) > 2 else None
        asyncio.run(create_migration_async(message))
    elif action == "upgrade":
        revision = sys.argv[2] if len(sys.argv) > 2 else "head"
        asyncio.run(upgrade_migration_async(revision))
    elif action == "downgrade":
        revision = sys.argv[2] if len(sys.argv) > 2 else "-1"
        asyncio.run(downgrade_migration_async(revision))
    elif action == "current":
        asyncio.run(show_current_revision_async())
    elif action == "history":
        asyncio.run(show_history_async())
    else:
        print(f"Unknown action: {action}")
        sys.exit(1)


if __name__ == '__main__':
    main()

