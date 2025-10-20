"""
데이터베이스 모델 정의
"""
from .user import User, Job, UserLevel, UserStatus
from .community import Post, Reply
from .learning import (
    LearningCategory, Chapter, Sentence, SimilarSentence,
    ChapterFeedback, SentenceFeedback
)
from .progress import UserProgress, SentenceProgress
from .scenario import Scenario, Role, ScenarioProgress, ScenarioFeedback

__all__ = [
    "User", "Job", "UserLevel", "UserStatus",
    "Post", "Reply",
    "LearningCategory", "Chapter", "Sentence", "SimilarSentence",
    "ChapterFeedback", "SentenceFeedback",
    "UserProgress", "SentenceProgress",
    "Scenario", "Role", "ScenarioProgress", "ScenarioFeedback"
]
