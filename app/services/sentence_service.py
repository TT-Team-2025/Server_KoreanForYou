"""
문장 관련 서비스
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List

from app.models.learning import Sentence, SimilarSentence
from app.schemas.learning import SentenceCreate, SentenceUpdate
from app.services.external_service import LLMService


class SentenceService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.llm_service = LLMService(db)

    async def get_sentence_by_id(self, sentence_id: int) -> Optional[Sentence]:
        """ID로 문장 조회"""
        result = await self.db.execute(select(Sentence).where(Sentence.sentence_id == sentence_id))
        return result.scalar_one_or_none()

    async def create_sentence(self, chapter_id: int) -> Sentence:
        """문장 생성"""
        # LLM 연동 로직 구현 후 확인
        ## 현재는 챕터의 decription을 프롬프트로 사용
        from app.models.learning import Chapter
        result = await self.db.execute(select(Chapter).where(Chapter.chapter_id == chapter_id))
        chapter = result.scalar_one_or_none()
        chapter_content = chapter.description if chapter else ""
        sentence_content = await request_to_llm(prompt=chapter_content)
        
        ## TTS 오디오 생성 로직 구현 후 확인
        sentence = Sentence(
            chapter_id=chapter_id,
            content=sentence_content,
            translated_content=await self.llm_service.translate_to_korean(sentence_content),
            tts_url=await self.llm_service.generate_tts_audio(sentence_content)
        )

        self.db.add(sentence)
        await self.db.commit()
        await self.db.refresh(sentence)

        return sentence
    
    async def update_sentence(self, sentence_id: int, sentence_update: SentenceUpdate) -> Optional[Sentence]:
        """문장 수정"""
        sentence = await self.get_sentence_by_id(sentence_id)
        if not sentence:
            return None
        
        update_data = sentence_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(sentence, field, value)

        await self.db.commit()
        await self.db.refresh(sentence)
        
        return sentence
    
    async def delete_sentence(self, sentence_id: int) -> bool:
        """문장 삭제"""
        sentence = await self.get_sentence_by_id(sentence_id)
        if not sentence:
            return False
        
        await self.db.delete(sentence)
        await self.db.commit()
        
        return True
    
    # 유사 문장 몇 개를 반환 할 것인지 num 구현 (기본값: 2)
    async def get_similar_sentences(self, sentence_id: int, num = 2) -> List[SimilarSentence]:
        """유사 문장 목록 조회"""
        result = await self.db.execute(
            select(SimilarSentence).where(
                SimilarSentence.sentence_id == sentence_id
            ).limit(num)
        )
        return list(result.scalars().all())

    async def create_similar_sentence(self, sentence_id: int) -> SimilarSentence:
        """유사 문장 생성"""
        # llm 연동 로직 구현 후 확인하기
        sentence_result = await self.db.execute(
            select(Sentence).where(Sentence.sentence_id == sentence_id)
        )
        sentence = sentence_result.scalar_one_or_none()
        sentence_content = sentence.content
        similar_sentence = self.llm_service.generate_similar_sentence(f'{sentence_content}와 유사한 문장을 생성해줘')

        self.db.add(similar_sentence)
        await self.db.commit()
        await self.db.refresh(similar_sentence)
        
        return similar_sentence
