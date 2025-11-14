"""
커뮤니티 게시글 더미데이터 생성 스크립트
카테고리별 게시글, 댓글, 대댓글 생성
"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from app.models.user import User
from app.models.community import Post, Reply, PostCategory
from app.core.config import settings
from datetime import datetime, timedelta
import random

# 더미 게시글 데이터
DUMMY_POSTS = [
    # Q&A 카테고리
    {"title": "한국어 학습 방법 질문", "content": "한국어를 처음 배우는데 어떤 방법이 가장 효과적일까요?", "category": PostCategory.QNA},
    {"title": "토픽 시험 준비 어떻게 하나요?", "content": "토픽 3급을 준비하고 있는데 추천 교재가 있을까요?", "category": PostCategory.QNA},
    {"title": "문법 질문드립니다", "content": "'-는 것'과 '-는 거'의 차이가 뭔가요?", "category": PostCategory.QNA},
    
    # 정보공유 카테고리
    {"title": "한국 문화 정보 공유", "content": "한국의 명절과 문화에 대해 알아보는 시간을 가져봐요!", "category": PostCategory.INFO_SHARE},
    {"title": "유용한 한국어 앱 추천", "content": "한국어 학습에 도움이 되는 앱들을 공유합니다.", "category": PostCategory.INFO_SHARE},
    {"title": "한국 여행 팁", "content": "한국 여행 시 알아두면 좋은 정보들을 모았습니다.", "category": PostCategory.INFO_SHARE},
    
    # 자유게시판
    {"title": "오늘의 일기", "content": "오늘 한국어 수업이 정말 재미있었어요!", "category": PostCategory.FREE},
    {"title": "인사드립니다", "content": "안녕하세요! 한국어를 배우고 있는 학생입니다.", "category": PostCategory.FREE},
    {"title": "주말 계획", "content": "이번 주말에는 한국 드라마를 보면서 공부하려고 해요.", "category": PostCategory.FREE},
    
    # 취업정보
    {"title": "한국 취업 준비하기", "content": "한국에서 취업을 준비하는 분들을 위한 정보입니다.", "category": PostCategory.JOB_INFO},
    {"title": "이력서 작성 팁", "content": "한국 기업에 지원할 때 이력서 작성 방법을 공유합니다.", "category": PostCategory.JOB_INFO},
]

# 더미 댓글 데이터
DUMMY_REPLIES = [
    "좋은 정보 감사합니다!",
    "저도 같은 고민이 있었어요.",
    "정말 도움이 되었습니다.",
    "추가로 궁금한 점이 있어요.",
    "저도 한번 시도해볼게요!",
    "감사합니다!",
    "좋은 글 감사합니다.",
    "도움이 많이 되었어요.",
    "저도 비슷한 경험이 있어요.",
    "추천해주셔서 감사합니다!",
]

async def create_dummy_data():
    """더미 데이터 생성"""
    engine = create_async_engine(settings.DATABASE_URL)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with SessionLocal() as session:
        # 사용자 조회 (최소 1명 필요)
        result = await session.execute(select(User).limit(10))
        users = list(result.scalars().all())
        
        if not users:
            print("❌ 사용자가 없습니다. 먼저 회원가입을 해주세요.")
            return
        
        print(f"✅ {len(users)}명의 사용자를 찾았습니다.")
        
        # 기존 게시글 확인
        result = await session.execute(select(Post))
        existing_posts = list(result.scalars().all())
        
        if existing_posts:
            print(f"⚠️  이미 {len(existing_posts)}개의 게시글이 있습니다.")
            print("기존 게시글과 댓글을 삭제하고 새로 생성합니다...")
            
            # 기존 댓글 삭제
            result = await session.execute(select(Reply))
            replies = list(result.scalars().all())
            for reply in replies:
                await session.delete(reply)
            
            # 기존 게시글 삭제
            for post in existing_posts:
                await session.delete(post)
            await session.commit()
            print("✅ 기존 게시글과 댓글을 삭제했습니다.")
        
        # 게시글 생성
        created_posts = []
        for i, post_data in enumerate(DUMMY_POSTS):
            user = random.choice(users)
            post = Post(
                user_id=user.user_id,
                title=post_data["title"],
                content=post_data["content"],
                category=post_data["category"],
                is_pinned=False,
                view_count=random.randint(0, 100),
                created_at=datetime.now() - timedelta(days=random.randint(0, 30))
            )
            session.add(post)
            created_posts.append(post)
            print(f"📝 게시글 생성: {post_data['title']} ({post_data['category'].value})")
        
        await session.commit()
        
        # 생성된 게시글 ID 가져오기
        for post in created_posts:
            await session.refresh(post)
        
        print(f"\n✅ {len(created_posts)}개의 게시글을 생성했습니다.\n")
        
        # 댓글 및 대댓글 생성
        total_replies = 0
        total_nested_replies = 0
        
        for post in created_posts:
            # 각 게시글당 2-5개의 댓글 생성
            num_replies = random.randint(2, 5)
            parent_replies = []
            
            for i in range(num_replies):
                user = random.choice(users)
                reply = Reply(
                    post_id=post.post_id,
                    user_id=user.user_id,
                    parent_reply_id=None,
                    content=random.choice(DUMMY_REPLIES),
                    created_at=datetime.now() - timedelta(days=random.randint(0, 20))
                )
                session.add(reply)
                await session.flush()  # ID를 얻기 위해 flush
                await session.refresh(reply)
                parent_replies.append(reply)
                total_replies += 1
                
                # 일부 댓글에 대댓글 추가 (50% 확률)
                if random.random() < 0.5 and len(parent_replies) > 0:
                    num_nested = random.randint(1, 2)
                    for j in range(num_nested):
                        nested_user = random.choice(users)
                        nested_reply = Reply(
                            post_id=post.post_id,
                            user_id=nested_user.user_id,
                            parent_reply_id=reply.reply_id,
                            content=random.choice(DUMMY_REPLIES),
                            created_at=datetime.now() - timedelta(days=random.randint(0, 15))
                        )
                        session.add(nested_reply)
                        total_nested_replies += 1
            
            print(f"💬 게시글 '{post.title}'에 댓글 {num_replies}개, 대댓글 {total_nested_replies}개 추가")
        
        await session.commit()
        
        print(f"\n✅ 더미 데이터 생성 완료!")
        print(f"   - 게시글: {len(created_posts)}개")
        print(f"   - 댓글: {total_replies}개")
        print(f"   - 대댓글: {total_nested_replies}개")
        print(f"   - 총 댓글 수: {total_replies + total_nested_replies}개")

if __name__ == "__main__":
    asyncio.run(create_dummy_data())

