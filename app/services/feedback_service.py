"""
피드백 관련 서비스
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
import re
from collections import Counter

from app.models.learning import ChapterFeedback, SentenceFeedback, Sentence
from app.models.scenario import ScenarioFeedback, ScenarioProgress
from app.schemas.learning import ChapterFeedbackCreate, SentenceFeedbackCreate
from app.services.external_service import LLMService
from app.models.progress import SentenceProgress

## 매개변수 수정 필요 -> FeedbackCreate!

class FeedbackService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.llm_service = LLMService(db)

    async def get_chapter_feedback(self, user_id: int, chapter_id: int) -> Optional[ChapterFeedback]:
        """챕터 피드백 조회"""
        result = await self.db.execute(
            select(ChapterFeedback).where(
                ChapterFeedback.user_id == user_id,
                ChapterFeedback.chapter_id == chapter_id
            )
        )
        return result.scalar_one_or_none()

    async def generate_chapter_feedback(
        self,
        user_id: int,
        chapter_id: int,
    ) -> ChapterFeedback:
        """챕터 피드백 생성 및 저장"""
        # 무조곤 생성하는 로직으로 변경
        ## 문장 학습을 도중에 중단했을 경우도 추후 고려 필요
        
        # 문장 피드백 조회
        feedback_result = await self.db.execute(
            select(SentenceFeedback).where(
                SentenceFeedback.user_id == user_id,
                SentenceFeedback.sentence.has(chapter_id=chapter_id)
            )
        )
        sentence_feedbacks = list(feedback_result.scalars().all())

        # 문장 id 조회
        sentence_ids = [fb.sentence_id for fb in sentence_feedbacks]

        # 문장 진행사항 조회
        if sentence_ids:
            progress_result = await self.db.execute(
                select(SentenceProgress).where(
                    SentenceProgress.sentence_id.in_(sentence_ids),
                    SentenceProgress.user_id == user_id
                )
            )
            sentences_progresses = list(progress_result.scalars().all())
        else:
            sentences_progresses = []
        
        ## 종합 평가, 문장별 성취도, ai 종합 피드백, 시간 기록

        # 발음 점수 계산 (평균)
        pronunciation_scores = [
            st.correct_word_count / st.total_word_count * 100
            for st in sentences_progresses
            if st.total_word_count and st.correct_word_count
        ]
        pronunciation_score = int(sum(pronunciation_scores) / len(pronunciation_scores)) if pronunciation_scores else 0

        # 정확도 점수 계산 (평균)
        accuracy_scores = [
            st.recognized_word_count / st.total_word_count * 100
            for st in sentences_progresses
            if st.total_word_count and st.recognized_word_count
        ]
        accuracy_score = int(sum(accuracy_scores) / len(accuracy_scores)) if accuracy_scores else 0

        # 약점 수집
        weaknesses_result = await self.db.execute(
            select(SentenceFeedback.weaknesses).where(
                SentenceFeedback.user_id == user_id,
                SentenceFeedback.sentence.has(chapter_id=chapter_id)
            )
        )
        weaknesses_raw = weaknesses_result.all()
        # JSON 배열들을 하나로 합치기 (중복 제거)
        weaknesses = list(set([
            w for sublist in weaknesses_raw
            for w in (sublist[0] if sublist[0] else [])
        ]))

        # LLM 서비스를 통한 종합 피드백 생성
        prompt = f"""
다음은 한국어 학습자의 챕터 학습 결과입니다:

- 완료한 문장 수: {len(sentences_progresses)}개
- 발음 점수: {pronunciation_score}점 (100점 만점)
- 정확도 점수: {accuracy_score}점 (100점 만점)
- 개선이 필요한 부분: {', '.join(weaknesses) if weaknesses else '없음'}

학습자에게 다음 내용을 포함한 종합 피드백을 3-4문장으로 작성해주세요:
1. 전반적인 학습 성과에 대한 긍정적인 평가
2. 발음과 정확도에 대한 구체적인 피드백
3. 개선이 필요한 부분에 대한 조언 (있는 경우)
4. 다음 학습을 위한 격려

한국어로 작성하고, 친근하고 격려하는 톤으로 작성해주세요.
"""

        # llm 서비스 연동
        llm_response = await self.llm_service.generate_text(
            prompt=prompt,
            prompt_role="user",
            max_tokens=500
        )
        summary_feedback = llm_response.get("content", "")

        # 시간 계산
        if sentences_progresses:
            # 첫 문장의 시작 시간과 마지막 문장의 종료 시간으로 총 학습 시간 계산
            sorted_progresses = sorted(sentences_progresses, key=lambda x: x.start_time or x.created_at)
            total_time_seconds = (sorted_progresses[-1].end_time - sorted_progresses[0].start_time).total_seconds() if sorted_progresses[-1].end_time else 0
            completion_time = sorted_progresses[-1].end_time
        else:
            total_time_seconds = 0
            completion_time = None

        # 생성
        feedback = ChapterFeedback(
            user_id=user_id,
            chapter_id=chapter_id,
            total_score=(pronunciation_score + accuracy_score) // 2,
            pronunciation_score=pronunciation_score,
            accuracy_score=accuracy_score,
            summary_feedback=summary_feedback,
            weaknesses=weaknesses,
            completion_time=completion_time,
            total_time=int(total_time_seconds),
            total_sentences=len(sentence_ids),
            completed_sentences=len(sentences_progresses)
        )
        self.db.add(feedback)

        await self.db.commit()
        await self.db.refresh(feedback)

        return feedback
    
    async def get_sentence_feedback(self, user_id: int, sentence_id: int) -> Optional[SentenceFeedback]:
        """문장 피드백 조회 (가장 최근 피드백 반환)"""
        result = await self.db.execute(
            select(SentenceFeedback)
            .join(SentenceProgress, SentenceFeedback.sentence_progress_id == SentenceProgress.progress_id)
            .where(
                SentenceFeedback.user_id == user_id,
                SentenceFeedback.sentence_id == sentence_id
            )
            .order_by(SentenceProgress.created_at.desc())
        )
        return result.scalar_one_or_none()
    

    async def generate_sentence_feedback(
        self,
        user_id: int,
        sentence_id: int,
        feedback_data: SentenceFeedbackCreate
    ) -> SentenceFeedback:
        """문장 피드백 생성 및 저장"""
        sentence_progress_id = feedback_data.sentence_progress_id

        # 문장 진행 상황 조회
        progress_result = await self.db.execute(
            select(SentenceProgress).where(
                SentenceProgress.progress_id == sentence_progress_id,
                SentenceProgress.user_id == user_id,
                SentenceProgress.sentence_id == sentence_id
            )
        )
        sentence_progress = progress_result.scalar_one_or_none()

        if not sentence_progress:
            raise ValueError("문장 진행 상황을 찾을 수 없습니다")

        # 원본 문장 조회
        sentence_result = await self.db.execute(
            select(Sentence).where(Sentence.sentence_id == sentence_id)
        )
        sentence = sentence_result.scalar_one_or_none()

        if not sentence:
            raise ValueError("문장을 찾을 수 없습니다")

        # 토큰화 함수 (progress_service와 동일한 로직)
        def tokenize(text: str):
            tokens = []
            for raw in text.split():
                cleaned = re.sub(r"[^\w가-힣]", "", raw).lower()
                if cleaned:
                    tokens.append(cleaned)
            return tokens

        # 원본 문장과 STT 결과 토큰화
        target_tokens = tokenize(sentence.content or "")
        stt_tokens = tokenize(sentence_progress.stt_transcript or "")

        # 단어 빈도 계산
        target_counter = Counter(target_tokens)
        stt_counter = Counter(stt_tokens)

        # missing_words: 원본에는 있지만 STT에 없거나 부족한 단어들
        missing_words = []
        for word, count in target_counter.items():
            remaining = count - min(count, stt_counter.get(word, 0))
            if remaining > 0:
                missing_words.extend([word] * remaining)

        # extra_words: STT에는 있지만 원본에 없거나 초과된 단어들
        extra_words = []
        for word, count in stt_counter.items():
            overflow = count - target_counter.get(word, 0)
            if overflow > 0:
                extra_words.extend([word] * overflow)

        # weaknesses 생성 (발음이 틀린 단어, 빠진 단어 등)
        weaknesses = []
        if missing_words:
            weaknesses.append(f"빠뜨린 단어: {', '.join(set(missing_words))}")
        if extra_words:
            weaknesses.append(f"추가된 단어: {', '.join(set(extra_words))}")

        # 정확도 계산
        if sentence_progress.total_word_count and sentence_progress.correct_word_count:
            accuracy_rate = (sentence_progress.correct_word_count / sentence_progress.total_word_count) * 100
            if accuracy_rate < 70:
                weaknesses.append("발음 정확도가 낮습니다")

        # LLM을 통한 구체적인 피드백 생성 (선택적)
        if weaknesses:
            prompt = f"""
다음은 한국어 학습자의 문장 발음 연습 결과입니다:

- 원본 문장: {sentence.content}
- 인식된 문장: {sentence_progress.stt_transcript}
- 전체 단어 수: {sentence_progress.total_word_count}
- 정확히 발음한 단어 수: {sentence_progress.correct_word_count}
- 개선이 필요한 부분:
{chr(10).join(f"  • {w}" for w in weaknesses)}

학습자에게 2-3문장으로 구체적인 개선 피드백을 작성해주세요:
1. 잘못 발음한 단어나 빠뜨린 단어에 대한 지적
2. 개선 방법에 대한 조언
3. 격려의 메시지

한국어로 작성하고, 친근하고 격려하는 톤으로 작성해주세요.
"""

            try:
                llm_response = await self.llm_service.generate_text(
                    prompt=prompt,
                    prompt_role="user",
                    max_tokens=300
                )
                ai_feedback = llm_response.get("content", "")
                if ai_feedback:
                    weaknesses.append(f"AI 피드백: {ai_feedback}")
            except Exception:
                # LLM 서비스 실패 시 무시하고 계속 진행
                pass

        # 피드백 생성
        feedback = SentenceFeedback(
            user_id=user_id,
            sentence_id=sentence_id,
            sentence_progress_id=sentence_progress_id,
            weaknesses=weaknesses if weaknesses else None
        )
        self.db.add(feedback)

        await self.db.commit()
        await self.db.refresh(feedback)

        return feedback
    
    async def get_scenario_feedback(self, user_id: int, scenario_id: int) -> Optional[ScenarioFeedback]:
        """시나리오 피드백 조회"""
        # 시나리오 진행 상황에서 최근 피드백 조회
        progress_result = await self.db.execute(
            select(ScenarioProgress).where(
                ScenarioProgress.user_id == user_id,
                ScenarioProgress.scenario_id == scenario_id
            ).order_by(ScenarioProgress.start_time.desc()).limit(1)
        )
        progress = progress_result.scalar_one_or_none()

        if not progress:
            return None

        feedback_result = await self.db.execute(
            select(ScenarioFeedback).where(
                ScenarioFeedback.log_id == progress.progress_id
            )
        )
        return feedback_result.scalar_one_or_none()
    
    ## 시나리오 피드백 생성 로직 - 구현중
    async def generate_scenario_feedback(
        self,
        log_id: int,
        feedback_data: dict
    ) -> ScenarioFeedback:
        """시나리오 피드백 생성"""
        feedback = ScenarioFeedback(
            log_id=log_id,
            **feedback_data
        )
        self.db.add(feedback)
        await self.db.commit()
        await self.db.refresh(feedback)
        
        return feedback
