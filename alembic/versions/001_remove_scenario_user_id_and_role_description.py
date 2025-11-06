"""remove scenario user_id and role description

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # scenarios 테이블에서 user_id 컬럼 삭제
    try:
        connection = op.get_bind()
        inspector = sa.inspect(connection)
        
        # scenarios 테이블 확인
        if 'scenarios' in inspector.get_table_names():
            columns = [col['name'] for col in inspector.get_columns('scenarios')]
            
            # user_id 컬럼이 있으면 외래키 제약조건 먼저 제거 후 컬럼 삭제
            if 'user_id' in columns:
                # 외래키 제약조건 찾기 및 제거
                foreign_keys = inspector.get_foreign_keys('scenarios')
                for fk in foreign_keys:
                    if 'user_id' in fk['constrained_columns']:
                        op.drop_constraint(fk['name'], 'scenarios', type_='foreignkey')
                        break
                
                # 컬럼 삭제
                op.drop_column('scenarios', 'user_id')
        
        # roles 테이블에서 description 컬럼 삭제
        if 'roles' in inspector.get_table_names():
            columns = [col['name'] for col in inspector.get_columns('roles')]
            
            if 'description' in columns:
                op.drop_column('roles', 'description')
                
    except Exception as e:
        print(f"Warning during upgrade: {e}")
        # 이미 삭제되었거나 다른 오류인 경우 계속 진행
        pass


def downgrade() -> None:
    # scenarios 테이블에 user_id 컬럼 다시 추가
    try:
        connection = op.get_bind()
        inspector = sa.inspect(connection)
        
        if 'scenarios' in inspector.get_table_names():
            columns = [col['name'] for col in inspector.get_columns('scenarios')]
            
            if 'user_id' not in columns:
                op.add_column('scenarios', 
                             sa.Column('user_id', sa.Integer(), nullable=True))
                
                # 외래키 제약조건 추가
                try:
                    op.create_foreign_key(
                        'fk_scenarios_user_id',
                        'scenarios',
                        'users',
                        ['user_id'],
                        ['user_id']
                    )
                except Exception:
                    pass
        
        # roles 테이블에 description 컬럼 다시 추가
        if 'roles' in inspector.get_table_names():
            columns = [col['name'] for col in inspector.get_columns('roles')]
            
            if 'description' not in columns:
                op.add_column('roles',
                             sa.Column('description', sa.Text(), nullable=True))
                
    except Exception as e:
        print(f"Warning during downgrade: {e}")
