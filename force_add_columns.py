"""
강제로 컬럼 추가 스크립트 (이미 존재해도 안전하게 재실행)
"""
import sys
from sqlalchemy import text
from app.core.database import engine
from app.core.config import settings


def force_add_columns():
    """scenario_progress 테이블에 컬럼 강제 추가"""
    print(f"📊 데이터베이스 URL: {settings.DATABASE_URL}")
    print("🔧 컬럼 추가 중...\n")
    
    with engine.connect() as conn:
        try:
            # 1. 기존 인덱스가 있으면 제거 (IF EXISTS로 안전하게)
            print("1️⃣ 기존 인덱스 제거 중...")
            conn.execute(text("""
                DROP INDEX IF EXISTS ix_scenario_progress_thread_id;
            """))
            
            # 2. 기존 컬럼이 있으면 제거 (안전하게)
            print("2️⃣ 기존 컬럼 제거 중...")
            conn.execute(text("""
                ALTER TABLE scenario_progress 
                DROP COLUMN IF EXISTS thread_id;
            """))
            
            conn.execute(text("""
                ALTER TABLE scenario_progress 
                DROP COLUMN IF EXISTS assistant_id;
            """))
            
            # 3. thread_id 컬럼 추가
            print("3️⃣ thread_id 컬럼 추가 중...")
            conn.execute(text("""
                ALTER TABLE scenario_progress 
                ADD COLUMN thread_id VARCHAR(255);
            """))
            
            # 4. assistant_id 컬럼 추가
            print("4️⃣ assistant_id 컬럼 추가 중...")
            conn.execute(text("""
                ALTER TABLE scenario_progress 
                ADD COLUMN assistant_id VARCHAR(255);
            """))
            
            # 5. thread_id에 unique index 생성
            print("5️⃣ thread_id 인덱스 생성 중...")
            conn.execute(text("""
                CREATE UNIQUE INDEX ix_scenario_progress_thread_id 
                ON scenario_progress(thread_id) 
                WHERE thread_id IS NOT NULL;
            """))
            
            conn.commit()
            print("\n✅ 컬럼 추가 완료!")
            print("   - thread_id VARCHAR(255)")
            print("   - assistant_id VARCHAR(255)")
            print("   - ix_scenario_progress_thread_id (UNIQUE INDEX)")
            print("\n💡 DBeaver에서 테이블을 새로고침(F5)하세요!")
            
        except Exception as e:
            conn.rollback()
            print(f"\n❌ 오류 발생: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)


if __name__ == "__main__":
    force_add_columns()

