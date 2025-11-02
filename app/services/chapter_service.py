"""
챕터 관련 서비스
"""
from sqlalchemy.orm import Session
from typing import Optional, List, Tuple
from sqlalchemy import and_

from app.models.learning import Chapter, Sentence, LearningCategory
from app.schemas.learning import ChapterCreate, ChapterUpdate
from app.models.progress import UserProgress
from app.services.llm_service import llm_service


class ChapterService:
    def __init__(self, db: Session):
        self.db = db
    
    def get_chapters(
        self, 
        user_id: int,
        job_id: Optional[int] = None, 
        level_id: Optional[int] = None,
        page: int = 1, 
        size: int = 10,
        group: Optional[bool] = all,
    ) -> Tuple[List[Chapter], int]:
        
        # 완료한 챕터 목록
        completed_chapters = self.db.query(UserProgress.chapter_id).filter(
            UserProgress.user_id == user_id,
            UserProgress.completion_rate == 100
        ).subquery()
        
        """챕터 목록 조회"""
        # 전체 조회
        coquery = []
        if group == "all":
            coquery = self.db.query(Chapter).filter(
                Chapter.is_active == True,
                Chapter.job_id == job_id if job_id is not None else True,
                Chapter.level_id == level_id if level_id is not None else True
            )
        # 완료하지 않은 챕터만
        elif group == "not_completed":
            coquery = self.db.query(Chapter).filter(
                    Chapter.is_active == True,                
                    Chapter.job_id == job_id if job_id is not None else True,
                    Chapter.level_id == level_id if level_id is not None else True,
                    ~Chapter.chapter_id.in_(completed_chapters)
            )
        # 완료된 챕터만
        elif group == "completed":
            coquery = completed_chapters
        query = coquery
        
        total = query.count()
        chapters = query.offset((page - 1) * size).limit(size).all()
        
        return chapters, total
    
    def get_chapter_by_id(self, chapter_id: int) -> Optional[Chapter]:
        """ID로 챕터 조회"""
        return self.db.query(Chapter).filter(Chapter.chapter_id == chapter_id).first()
    
    def create_chapter(self, chapter_data: ChapterCreate) -> Chapter:
        """챕터 생성"""
        
        # 카테고리 기반으로 조회해야함
        # LLM 서비스 구현 확인 후 재검토 
        chapter = llm_service.generate_chapter_content(
            category_id=chapter_data.category_id
        )
        
        self.db.add(chapter)
        self.db.commit()
        self.db.refresh(chapter)
        
        return chapter
    
    # 추후 디벨롭 필요
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
    
    # 추후 디벨롭 필요
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
