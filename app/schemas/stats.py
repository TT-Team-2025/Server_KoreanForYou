"""
통계 관련 스키마
"""
from pydantic import BaseModel
from typing import Optional, List, Any


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
    total_score: Optional[int] = None


class ChapterFeedbackBrief(BaseModel):
    feedback_id: int
    chapter_id: int
    chapter_title: Optional[str] = None
    completed_sentences: int
    total_sentences: int
    total_score: Optional[int] = None
    completed_date: Optional[str] = None


class ChapterFeedbackDetail(BaseModel):
    feedback_id: int
    chapter_id: int
    chapter_title: Optional[str] = None
    total_sentences: int
    completed_sentences: int
    completion_rate: float
    total_score: Optional[int] = None
    pronunciation_score: Optional[int] = None
    accuracy_score: Optional[int] = None
    summary_feedback: Optional[str] = None
    weaknesses: Optional[List[Any]] = None
    total_time: Optional[int] = None
    created_at: Optional[str] = None


class RecentLearningActivity(BaseModel):
    activity_type: str
    activity_id: int
    title: Optional[str] = None
    description: Optional[str] = None
    date: Optional[str] = None
    total_score: Optional[int] = None
    completion_status: Optional[str] = None


class LearningDatesByMonth(BaseModel):
    month: str
    dates: List[str]

