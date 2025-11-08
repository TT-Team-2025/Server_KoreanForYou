"""
통계 관련 서비스
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List, Dict

from app.models.scenario import Scenario, ScenarioProgress, CompletionStatus


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
            .options(selectinload(Scenario.scenario_progress))
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

            end_time = completed_progress.end_time.date().isoformat() if completed_progress.end_time else None
            scenario_list.append(
                {
                    "title": scenario.title,
                    "description": scenario.description,
                    "date": end_time,
                }
            )

        return scenario_list
    