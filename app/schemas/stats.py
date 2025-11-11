"""
통계 관련 스키마
"""
from pydantic import BaseModel
from typing import Optional


class LearningSummaryResponse(BaseModel):
    total_study_minutes: int
    continuous_learning_days: int
    ai_turn_count: int
    completed_sentence_count: int


class RecentScenarioItem(BaseModel):
    progress_id: int
    title: str
    description: Optional[str] = None
    date: Optional[str] = None
    completion_status: Optional[str] = None

