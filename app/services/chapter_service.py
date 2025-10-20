"""
챕터 관련 서비스
"""
from sqlalchemy.orm import Session
from typing import Optional, List, Tuple
from sqlalchemy import and_

from app.models.learning import Chapter, Sentence, LearningCategory
from app.schemas.learning import ChapterCreate, ChapterUpdate


class ChapterService:
    def __init__(self, db: Session):
        self.db = db
    
    def get_chapters(
        self, 
        job_id: Optional[int] = None, 
        level_id: Optional[int] = None,
        page: int = 1, 
        size: int = 20
    ) -> Tuple[List[Chapter], int]:
        """챕터 목록 조회"""
        query = self.db.query(Chapter).filter(Chapter.is_active == True)
        
        if job_id is not None:
            query = query.filter(Chapter.job_id == job_id)
        
        if level_id is not None:
            query = query.filter(Chapter.level_id == level_id)
        
        total = query.count()
        chapters = query.offset((page - 1) * size).limit(size).all()
        
        return chapters, total
    
    def get_chapter_by_id(self, chapter_id: int) -> Optional[Chapter]:
        """ID로 챕터 조회"""
        return self.db.query(Chapter).filter(Chapter.chapter_id == chapter_id).first()
    
    def create_chapter(self, chapter_data: ChapterCreate) -> Chapter:
        """챕터 생성"""
        chapter = Chapter(**chapter_data.dict())
        
        self.db.add(chapter)
        self.db.commit()
        self.db.refresh(chapter)
        
        return chapter
    
    def update_chapter(self, chapter_id: int, chapter_update: ChapterUpdate) -> Optional[Chapter]:
        """챕터 수정"""
        chapter = self.get_chapter_by_id(chapter_id)
        if not chapter:
            return None
        
        update_data = chapter_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(chapter, field, value)
        
        self.db.commit()
        self.db.refresh(chapter)
        
        return chapter
    
    def delete_chapter(self, chapter_id: int) -> bool:
        """챕터 삭제 (소프트 삭제)"""
        chapter = self.get_chapter_by_id(chapter_id)
        if not chapter:
            return False
        
        chapter.is_active = False
        self.db.commit()
        
        return True
    
    def get_chapter_sentences(
        self, 
        chapter_id: int, 
        page: int = 1, 
        size: int = 20
    ) -> Tuple[List[Sentence], int]:
        """챕터 내 문장 목록 조회"""
        query = self.db.query(Sentence).filter(Sentence.chapter_id == chapter_id)
        
        total = query.count()
        sentences = query.offset((page - 1) * size).limit(size).all()
        
        return sentences, total
    
    def get_learning_categories(self, job_id: Optional[int] = None) -> List[LearningCategory]:
        """학습 카테고리 조회"""
        query = self.db.query(LearningCategory)
        
        if job_id is not None:
            query = query.filter(LearningCategory.job_id == job_id)
        
        return query.all()
