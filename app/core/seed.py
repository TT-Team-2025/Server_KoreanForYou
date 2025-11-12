"""
데이터베이스 초기 데이터 삽입
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import Job, UserLevel
from app.models.learning import LearningCategory


# Job 매핑 데이터
JOB_MAPPING = {
    "공통": 0,
    "주방보조": 1,
    "서빙": 2,
    "바리스타": 3,
    "캐셔": 4,
    "배달": 5,
    "주방장": 6,
    "설거지": 7,
}

# Level 데이터
LEVEL_MAPPING = {
    0: "공통",
    1: "초급",
    2: "중급",
    3: "고급",
}


async def seed_jobs(session: AsyncSession):
    """Job 테이블 초기 데이터 삽입"""
    print("[SEED] Checking jobs table...")

    for job_name, job_id in JOB_MAPPING.items():
        # 이미 존재하는지 확인
        result = await session.execute(
            select(Job).where(Job.job_id == job_id)
        )
        existing_job = result.scalar_one_or_none()

        if existing_job is None:
            # 새로운 job 추가
            new_job = Job(
                job_id=job_id,
                job_name=job_name,
                description=f"{job_name} 직무"
            )
            session.add(new_job)
            print(f"[SEED] Added job: {job_name} (ID: {job_id})")
        else:
            print(f"[SEED] Job already exists: {job_name} (ID: {job_id})")

    await session.commit()


async def seed_categories(session: AsyncSession):
    """LearningCategory 테이블 초기 데이터 삽입"""
    print("[SEED] Checking learning_categories table...")

    for job_name, job_id in JOB_MAPPING.items():
        # 이미 존재하는지 확인
        result = await session.execute(
            select(LearningCategory).where(
                LearningCategory.category_id == job_id
            )
        )
        existing_category = result.scalar_one_or_none()

        if existing_category is None:
            # 새로운 category 추가
            new_category = LearningCategory(
                category_id=job_id,
                job_id=job_id,
                content=f"{job_name} 학습"
            )
            session.add(new_category)
            print(f"[SEED] Added category: {job_name} (ID: {job_id})")
        else:
            print(f"[SEED] Category already exists: {job_name} (ID: {job_id})")

    await session.commit()


async def seed_levels(session: AsyncSession):
    """UserLevel 테이블 초기 데이터 삽입"""
    print("[SEED] Checking user_level table...")

    for level_id, level_name in LEVEL_MAPPING.items():
        # 이미 존재하는지 확인
        result = await session.execute(
            select(UserLevel).where(UserLevel.level_id == level_id)
        )
        existing_level = result.scalar_one_or_none()

        if existing_level is None:
            # 새로운 level 추가
            new_level = UserLevel(
                level_id=level_id,
                level_name=level_name,
                description=f"{level_name} 레벨"
            )
            session.add(new_level)
            print(f"[SEED] Added level: {level_name} (ID: {level_id})")
        else:
            print(f"[SEED] Level already exists: {level_name} (ID: {level_id})")

    await session.commit()


async def seed_all(session: AsyncSession):
    """모든 초기 데이터 삽입"""
    try:
        print("[SEED] Starting database seeding...")

        await seed_jobs(session)
        await seed_categories(session)
        await seed_levels(session)

        print("[SEED] Database seeding completed successfully!")
    except Exception as e:
        print(f"[SEED] Error during seeding: {e}")
        await session.rollback()
        raise
