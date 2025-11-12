"""
통계 관련 서비스
"""
from datetime import datetime, timedelta, date
from typing import List, Dict, Set, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.models.scenario import Scenario, ScenarioProgress, CompletionStatus
from app.models.learning import ChapterFeedback
from app.models.progress import UserProgress, SentenceProgress
from app.schemas.stats import LearningSummaryResponse


class StatsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_recent_scenarios(self, limit: int = 10) -> List[Dict[str, str]]:
        """완료된 시나리오 목록 반환"""
        result = await self.db.execute(
            select(Scenario)
            .join(ScenarioProgress)
            .where(ScenarioProgress.completion_status == CompletionStatus.COMPLETED)
            .order_by(ScenarioProgress.end_time.desc())
            .options(
                selectinload(Scenario.scenario_progress).selectinload(
                    ScenarioProgress.scenario_feedback
                )
            )
            .limit(limit)
        )
        scenarios = result.scalars().all()

        scenario_list: List[Dict[str, str]] = []
        for scenario in scenarios:
            completed_progress = next(
                (
                    progress for progress in scenario.scenario_progress
                    if progress.completion_status == CompletionStatus.COMPLETED
                ),
                None
            )
            if not completed_progress:
                continue

            progress_id = completed_progress.progress_id
            end_time = completed_progress.end_time.date().isoformat() if completed_progress.end_time else None
            feedback = completed_progress.scenario_feedback[0] if completed_progress.scenario_feedback else None

            scenario_list.append(
                {
                    "progress_id": progress_id,
                    "title": scenario.title,
                    "description": scenario.description,
                    "date": end_time,
                    "completion_status": completed_progress.completion_status.value,
                    "total_score": feedback.total_score if feedback else None,
                }
            )

        return scenario_list

    async def get_recent_chapter_feedbacks(
        self,
        user_id: int,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """최근 완료한 챕터 학습 피드백 목록"""
        result = await self.db.execute(
            select(ChapterFeedback)
            .where(ChapterFeedback.user_id == user_id)
            .order_by(ChapterFeedback.created_at.desc())
            .options(selectinload(ChapterFeedback.chapter))
            .limit(limit)
        )
        feedbacks = list(result.scalars().all())

        unique_map: Dict[int, ChapterFeedback] = {}
        for fb in feedbacks:
            if fb.chapter_id not in unique_map:
                unique_map[fb.chapter_id] = fb

        feedback_list: List[Dict[str, Any]] = []
        for fb in unique_map.values():
            chapter = fb.chapter
            completed_date = fb.created_at.date().isoformat() if fb.created_at else None
            feedback_list.append(
                {
                    "feedback_id": fb.feedback_id,
                    "chapter_id": fb.chapter_id,
                    "chapter_title": chapter.title if chapter else None,
                    "completed_sentences": fb.completed_sentences,
                    "total_sentences": fb.total_sentences,
                    "total_score": fb.total_score,
                    "completed_date": completed_date,
                }
            )

        return feedback_list

    async def get_learning_summary(self, user_id: int) -> LearningSummaryResponse:
        """사용자 학습 요약 정보 조회"""
        total_sentence_time_result = await self.db.execute(
            select(func.coalesce(func.sum(SentenceProgress.total_time), 0)).where(
                SentenceProgress.user_id == user_id,
                SentenceProgress.total_time.isnot(None),
            )
        )
        total_sentence_time = int(total_sentence_time_result.scalar() or 0)

        total_scenario_time_result = await self.db.execute(
            select(func.coalesce(func.sum(ScenarioProgress.total_time), 0)).where(
                ScenarioProgress.user_id == user_id,
                ScenarioProgress.total_time.isnot(None),
            )
        )
        total_scenario_time = int(total_scenario_time_result.scalar() or 0)

        total_study_seconds = total_sentence_time + total_scenario_time
        total_study_minutes = total_study_seconds // 60

        total_turn_count_result = await self.db.execute(
            select(func.coalesce(func.sum(ScenarioProgress.turn_count), 0)).where(
                ScenarioProgress.user_id == user_id,
                ScenarioProgress.turn_count.isnot(None),
            )
        )
        ai_turn_count = int(total_turn_count_result.scalar() or 0)

        completed_sentences_result = await self.db.execute(
            select(func.count()).select_from(SentenceProgress).where(
                SentenceProgress.user_id == user_id,
                SentenceProgress.is_completed == True,
            )
        )
        completed_sentence_count = int(completed_sentences_result.scalar() or 0)

        learning_dates = await self._collect_learning_dates(user_id)
        print(f"learning_dates: {learning_dates}")
        continuous_learning_days = self._calculate_streak(learning_dates)

        return LearningSummaryResponse(
            total_study_minutes=total_study_minutes,
            continuous_learning_days=continuous_learning_days,
            ai_turn_count=ai_turn_count,
            completed_sentence_count=completed_sentence_count,
        )

    async def _collect_learning_dates(self, user_id: int) -> Set[date]:
        """사용자가 학습 활동을 수행한 날짜 집합을 수집"""
        dates: Set[date] = set()

        user_progress_dates_result = await self.db.execute(
            select(func.date(UserProgress.last_access_at)).where(
                UserProgress.user_id == user_id,
                UserProgress.last_access_at.isnot(None),
            )
        )
        for row in user_progress_dates_result:
            day = row[0]
            if isinstance(day, date):
                dates.add(day)

        sentence_dates_result = await self.db.execute(
            select(func.date(SentenceProgress.end_time)).where(
                SentenceProgress.user_id == user_id,
                SentenceProgress.end_time.isnot(None),
            )
        )
        for row in sentence_dates_result:
            day = row[0]
            if isinstance(day, date):
                dates.add(day)

        scenario_dates_result = await self.db.execute(
            select(
                func.date(
                    func.coalesce(
                        ScenarioProgress.end_time,
                        ScenarioProgress.start_time,
                    )
                )
            ).where(
                ScenarioProgress.user_id == user_id,
                func.coalesce(
                    ScenarioProgress.end_time,
                    ScenarioProgress.start_time,
                ).isnot(None),
            )
        )
        for row in scenario_dates_result:
            day = row[0]
            if isinstance(day, date):
                dates.add(day)

        return dates

    def _calculate_streak(self, dates: Set[date]) -> int:
        """학습 날짜 집합을 기반으로 연속 학습 일수 계산"""
        if not dates:
            return 0

        today = datetime.utcnow().date()
        reference = today if today in dates else max(dates)

        streak = 0
        current = reference
        while current in dates:
            streak += 1
            current -= timedelta(days=1)

        return streak
