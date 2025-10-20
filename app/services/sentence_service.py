"""
문장 관련 서비스
"""
from sqlalchemy.orm import Session
from typing import Optional, List

from app.models.learning import Sentence, SimilarSentence
from app.schemas.learning import SentenceCreate, SentenceUpdate


class SentenceService:
    def __init__(self, db: Session):
        self.db = db
    
    def get_sentence_by_id(self, sentence_id: int) -> Optional[Sentence]:
        """ID로 문장 조회"""
        return self.db.query(Sentence).filter(Sentence.sentence_id == sentence_id).first()
    
    def create_sentence(self, sentence_data: SentenceCreate) -> Sentence:
        """문장 생성"""
        sentence = Sentence(**sentence_data.dict())
        
        self.db.add(sentence)
        self.db.commit()
        self.db.refresh(sentence)
        
        return sentence
    
    def update_sentence(self, sentence_id: int, sentence_update: SentenceUpdate) -> Optional[Sentence]:
        """문장 수정"""
        sentence = self.get_sentence_by_id(sentence_id)
        if not sentence:
            return None
        
        update_data = sentence_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(sentence, field, value)
        
        self.db.commit()
        self.db.refresh(sentence)
        
        return sentence
    
    def delete_sentence(self, sentence_id: int) -> bool:
        """문장 삭제"""
        sentence = self.get_sentence_by_id(sentence_id)
        if not sentence:
            return False
        
        self.db.delete(sentence)
        self.db.commit()
        
        return True
    
    def get_similar_sentences(self, sentence_id: int) -> List[SimilarSentence]:
        """유사 문장 목록 조회"""
        return self.db.query(SimilarSentence).filter(
            SimilarSentence.sentence_id == sentence_id
        ).all()
    
    def create_similar_sentence(self, similar_sentence_data: dict) -> SimilarSentence:
        """유사 문장 생성"""
        similar_sentence = SimilarSentence(**similar_sentence_data)
        
        self.db.add(similar_sentence)
        self.db.commit()
        self.db.refresh(similar_sentence)
        
        return similar_sentence
