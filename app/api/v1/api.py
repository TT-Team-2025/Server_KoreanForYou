"""
API v1 라우터 통합
"""
from fastapi import APIRouter

from app.api.v1.endpoints import auth, users, chapters, sentences, progress, scenarios, community, external, feedback, stats

api_router = APIRouter()

# 인증 관련
api_router.include_router(auth.router, prefix="/auth", tags=["인증"])

# 사용자 관련
api_router.include_router(users.router, prefix="/users", tags=["사용자"])

# 학습 콘텐츠 관련
api_router.include_router(chapters.router, prefix="/chapters", tags=["챕터"])
api_router.include_router(sentences.router, prefix="/sentences", tags=["문장"])

# 학습 진행 관련
api_router.include_router(progress.router, prefix="/progress", tags=["학습진행"])

# 시나리오 관련
api_router.include_router(scenarios.router, prefix="/scenarios", tags=["시나리오"])

# 커뮤니티 관련
api_router.include_router(community.router, prefix="/posts", tags=["커뮤니티"])

# 외부 API 서비스
api_router.include_router(external.router, prefix="/external", tags=["외부서비스"])

# 피드백 관련
api_router.include_router(feedback.router, prefix="/feedback", tags=["피드백"])

# 통계 관련
api_router.include_router(stats.router, prefix="/stats", tags=["통계"])
