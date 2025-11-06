"""
통계 관련 서비스
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Dict, Any, Optional

from app.models.user import User, UserStatus
from app.models.learning import Chapter, ChapterFeedback
from app.models.scenario import Scenario, ScenarioFeedback, ScenarioProgress
from app.models.progress import UserProgress, SentenceProgress


class StatsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user_stats(self, user_id: int) -> Optional[Dict[str, Any]]:
        """사용자 전체 통계 조회"""
        user_status_result = await self.db.execute(
            select(UserStatus).where(UserStatus.user_id == user_id)
        )
        user_status = user_status_result.scalar_one_or_none()

        if not user_status:
            return None

        # 추가 통계 계산
        total_chapters_result = await self.db.execute(
            select(func.count()).select_from(Chapter).where(Chapter.is_active == True)
        )
        total_chapters = total_chapters_result.scalar() or 0

        completed_chapters_result = await self.db.execute(
            select(func.count()).select_from(UserProgress).where(
                UserProgress.user_id == user_id,
                UserProgress.completion_rate >= 100
            )
        )
        completed_chapters = completed_chapters_result.scalar() or 0

        total_sentences_result = await self.db.execute(
            select(func.count()).select_from(SentenceProgress).where(
                SentenceProgress.user_id == user_id
            )
        )
        total_sentences = total_sentences_result.scalar() or 0

        completed_sentences_result = await self.db.execute(
            select(func.count()).select_from(SentenceProgress).where(
                SentenceProgress.user_id == user_id,
                SentenceProgress.is_completed == True
            )
        )
        completed_sentences = completed_sentences_result.scalar() or 0

        # 평균 점수 계산
        avg_score_result = await self.db.execute(
            select(func.avg(ChapterFeedback.total_score)).where(
                ChapterFeedback.user_id == user_id
            )
        )
        avg_score = avg_score_result.scalar()
        
        return {
            "user_id": user_id,
            "total_study_time": user_status.total_study_time,
            "total_sentences_completed": user_status.total_sentences_completed,
            "total_scenarios_completed": user_status.total_scenarios_completed,
            "average_score": float(avg_score) if avg_score else None,
            "current_access_days": user_status.current_access_days,
            "longest_access_days": user_status.longest_access_days,
            "last_study_date": user_status.last_study_date.isoformat() if user_status.last_study_date else None,
            "total_chapters": total_chapters,
            "completed_chapters": completed_chapters,
            "total_sentences": total_sentences,
            "completed_sentences": completed_sentences,
            "completion_rate": (completed_chapters / total_chapters * 100) if total_chapters > 0 else 0
        }
    
    async def get_chapter_stats(self, chapter_id: int) -> Optional[Dict[str, Any]]:
        """챕터별 통계 조회"""
        chapter_result = await self.db.execute(
            select(Chapter).where(Chapter.chapter_id == chapter_id)
        )
        chapter = chapter_result.scalar_one_or_none()
        if not chapter:
            return None

        # 챕터를 학습한 사용자 수
        total_users_result = await self.db.execute(
            select(func.count()).select_from(UserProgress).where(
                UserProgress.chapter_id == chapter_id
            )
        )
        total_users = total_users_result.scalar() or 0

        # 챕터를 완료한 사용자 수
        completed_users_result = await self.db.execute(
            select(func.count()).select_from(UserProgress).where(
                UserProgress.chapter_id == chapter_id,
                UserProgress.completion_rate >= 100
            )
        )
        completed_users = completed_users_result.scalar() or 0

        # 평균 점수
        avg_score_result = await self.db.execute(
            select(func.avg(ChapterFeedback.total_score)).where(
                ChapterFeedback.chapter_id == chapter_id
            )
        )
        avg_score = avg_score_result.scalar()

        # 평균 완료 시간
        avg_completion_time_result = await self.db.execute(
            select(func.avg(ChapterFeedback.completion_time)).where(
                ChapterFeedback.chapter_id == chapter_id
            )
        )
        avg_completion_time = avg_completion_time_result.scalar()
        
        return {
            "chapter_id": chapter_id,
            "chapter_title": chapter.title,
            "total_users": total_users,
            "completed_users": completed_users,
            "completion_rate": (completed_users / total_users * 100) if total_users > 0 else 0,
            "average_score": float(avg_score) if avg_score else None,
            "average_completion_time": float(avg_completion_time) if avg_completion_time else None,
            "total_feedback_count": (await self.db.execute(
                select(func.count()).select_from(ChapterFeedback).where(
                    ChapterFeedback.chapter_id == chapter_id
                )
            )).scalar() or 0
        }
    
    async def get_scenario_stats(self, scenario_id: int) -> Optional[Dict[str, Any]]:
        """시나리오별 통계 조회"""
        scenario_result = await self.db.execute(
            select(Scenario).where(Scenario.scenario_id == scenario_id)
        )
        scenario = scenario_result.scalar_one_or_none()
        if not scenario:
            return None

        # 시나리오를 수행한 사용자 수
        total_users_result = await self.db.execute(
            select(func.count()).select_from(ScenarioProgress).where(
                ScenarioProgress.scenario_id == scenario_id
            )
        )
        total_users = total_users_result.scalar() or 0

        # 시나리오를 완료한 사용자 수
        completed_users_result = await self.db.execute(
            select(func.count()).select_from(ScenarioProgress).where(
                ScenarioProgress.scenario_id == scenario_id,
                ScenarioProgress.completion_status == "완료"
            )
        )
        completed_users = completed_users_result.scalar() or 0

        # 평균 점수
        avg_score_result = await self.db.execute(
            select(func.avg(ScenarioFeedback.total_score)).select_from(ScenarioFeedback).join(
                ScenarioProgress, ScenarioFeedback.log_id == ScenarioProgress.progress_id
            ).where(
                ScenarioProgress.scenario_id == scenario_id
            )
        )
        avg_score = avg_score_result.scalar()
        
        return {
            "scenario_id": scenario_id,
            "scenario_title": scenario.title,
            "total_users": total_users,
            "completed_users": completed_users,
            "completion_rate": (completed_users / total_users * 100) if total_users > 0 else 0,
            "average_score": float(avg_score) if avg_score else None,
            "total_feedback_count": (await self.db.execute(
                select(func.count()).select_from(ScenarioFeedback).join(
                    ScenarioProgress, ScenarioFeedback.log_id == ScenarioProgress.progress_id
                ).where(
                    ScenarioProgress.scenario_id == scenario_id
                )
            )).scalar() or 0
        }
    
    async def get_api_usage_stats(self) -> Dict[str, Any]:
        """API 사용량 통계 조회"""
        # TODO: 실제 API 사용량 추적 구현
        # 현재는 모의 데이터 반환
        
        return {
            "tts_requests": 1250,
            "stt_requests": 980,
            "llm_requests": 450,
            "total_requests": 2680,
            "daily_average": 89.3,
            "most_used_service": "TTS",
            "usage_by_hour": {
                "00": 12, "01": 8, "02": 5, "03": 3, "04": 2, "05": 4,
                "06": 15, "07": 45, "08": 78, "09": 95, "10": 88, "11": 92,
                "12": 85, "13": 90, "14": 95, "15": 88, "16": 82, "17": 75,
                "18": 68, "19": 55, "20": 42, "21": 35, "22": 28, "23": 18
            }
        }
