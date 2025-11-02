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
    
    def create_sentence(self, chapter_id: int) -> Sentence:
        """문장 생성"""
        # LLM 연동 로직 구현 후 확인
        ## 현재는 챕터의 decription을 프롬프트로 사용
        chapter_content = self.db.query(Chapter).filter(Chapter.chapter_id == chapter_id).first().description
        sentence_content = request_to_llm(prompt=chapter_content)
        
        ## TTS 오디오 생성 로직 구현 후 확인
        sentence = Sentence(
            chapter_id=chapter_id,
            content=sentence_content,
            translated_content=llm_service.translate_to_korean(sentence_content),
            tts_url=llm_service.generate_tts_audio(sentence_content)
        )
        
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
    
    # 유사 문장 몇 개를 반환 할 것인지 num 구현 (기본값: 2)
    def get_similar_sentences(self, sentence_id: int, num = 2) -> List[SimilarSentence]:
        """유사 문장 목록 조회"""
        return self.db.query(SimilarSentence).filter(
            SimilarSentence.sentence_id == sentence_id
        ).limit(num).all()
    
    def create_similar_sentence(self, sentence_id: 2) -> SimilarSentence:
        """유사 문장 생성"""
        # llm 연동 로직 구현 후 확인하기
        sentence_content = self.db.query(Sentence).filter(Sentence.sentence_id == sentence_id).first().content
        similar_sentence = llm_service.generate_similar_sentence(f'{sentence_content}와 유사한 문장을 생성해줘')
        
        self.db.add(similar_sentence)
        self.db.commit()
        self.db.refresh(similar_sentence)
        
        return similar_sentence
