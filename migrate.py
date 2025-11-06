"""Alembic 마이그레이션 실행 및 생성 스크립트"""
import sys
import os

# 프로젝트 루트 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 환경 변수 설정
from app.core.config import settings
if not os.environ.get('DATABASE_URL'):
    os.environ['DATABASE_URL'] = settings.DATABASE_URL

from alembic.config import Config
from alembic import command

def create_migration(message: str = None):
    """새 마이그레이션 파일 생성 (autogenerate)"""
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

def upgrade_migration(revision: str = "head"):
    """마이그레이션 적용"""
    cfg = Config()
    cfg.set_main_option("script_location", "alembic")
    cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
    
    print(f"Applying migrations up to: {revision}")
    try:
        command.upgrade(cfg, revision)
        print("✓ Migration completed successfully!")
    except Exception as e:
        print(f"✗ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

def downgrade_migration(revision: str = "-1"):
    """마이그레이션 롤백"""
    cfg = Config()
    cfg.set_main_option("script_location", "alembic")
    cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
    
    print(f"Downgrading to: {revision}")
    try:
        command.downgrade(cfg, revision)
        print("✓ Downgrade completed successfully!")
    except Exception as e:
        print(f"✗ Downgrade failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

def main():
    """메인 함수"""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python migrate.py create [message]  - Create new migration (autogenerate)")
        print("  python migrate.py upgrade [revision] - Apply migrations (default: head)")
        print("  python migrate.py downgrade [revision] - Rollback migrations (default: -1)")
        sys.exit(1)
    
    action = sys.argv[1]
    
    if action == "create":
        message = sys.argv[2] if len(sys.argv) > 2 else None
        create_migration(message)
    elif action == "upgrade":
        revision = sys.argv[2] if len(sys.argv) > 2 else "head"
        upgrade_migration(revision)
    elif action == "downgrade":
        revision = sys.argv[2] if len(sys.argv) > 2 else "-1"
        downgrade_migration(revision)
    else:
        print(f"Unknown action: {action}")
        sys.exit(1)

if __name__ == '__main__':
    main()
