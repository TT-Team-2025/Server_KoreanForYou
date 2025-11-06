"""
챕터 관련 서비스
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional, List, Tuple
import json
import ast, re

from app.models.learning import Chapter, Sentence, LearningCategory
from app.models.user import Job
from app.schemas.learning import ChapterCreate, ChapterUpdate, LearningCategoryResponse
from app.models.progress import UserProgress
from app.services.external_service import LLMService


class ChapterService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.llm_service = LLMService(db)
    
    async def get_chapters(
        self,
        user_id: int,
        category_id: int,
        level_id: int,
        page: int = 1,
        size: int = 10,
        group: Optional[str] = "all",
    ) -> Tuple[List[Chapter], int]:
        """챕터 목록 조회"""

        # 완료한 챕터 ID 목록 조회
        completed_result = await self.db.execute(
            select(UserProgress.chapter_id).where(
                UserProgress.user_id == user_id,
                UserProgress.completion_rate == 100
            )
        )
        completed_chapter_ids = [row[0] for row in completed_result.all()]

        # 기본 쿼리 구성
        stmt = select(Chapter).where(
            Chapter.is_active == True,
            Chapter.category_id == category_id,
            Chapter.level_id == level_id
        )

        # 그룹별 필터링
        if group == "not_completed":
            stmt = stmt.where(~Chapter.chapter_id.in_(completed_chapter_ids)) if completed_chapter_ids else stmt
        elif group == "completed":
            if not completed_chapter_ids:
                return [], 0
            stmt = stmt.where(Chapter.chapter_id.in_(completed_chapter_ids))

        # 전체 개수 조회
        count_stmt = select(func.count()).select_from(stmt.alias())
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar() or 0

        # 페이징 처리
        stmt = stmt.offset((page - 1) * size).limit(size)
        result = await self.db.execute(stmt)
        chapters = list(result.scalars().all())

        return chapters, total
    
    async def ensure_chapters_exist(
        self,
        user_id: int,
        category_id: int,
        level_id: int,
        page: int = 1,
        size: int = 10,
        group: str = "all",
    ) -> Tuple[List[Chapter], int]:
        """
        챕터가 없을 경우 LLM을 통해 자동 생성 후 재조회
        """
        chapters, total = await self.get_chapters(
            user_id=user_id,
            category_id=category_id,
            level_id=level_id,
            page=page,
            size=size,
            group=group,
        )

        if total == 0:
            await self.create_chapter(category_id=category_id, level_id=level_id)
            chapters, total = await self.get_chapters(
                user_id=user_id,
                category_id=category_id,
                level_id=level_id,
                page=page,
                size=size,
                group=group,
            )

        return chapters, total

    # 소프트 딜리트 반영
    async def get_chapter_by_id(self, chapter_id: int) -> Optional[Chapter]:
        """ID로 챕터 조회"""
        result = await self.db.execute(select(Chapter).where(Chapter.chapter_id == chapter_id))
        chapter = result.scalar_one_or_none()
        
        if not chapter:
            return False
        
        if not chapter.is_active:
            return False
        
        return chapter
    
    async def create_chapter(self, chapter_data: ChapterCreate):
        """LLM을 활용한 챕터 생성"""
        category_result = await self.db.execute(
            select(LearningCategory).where(LearningCategory.category_id == chapter_data.category_id)
        )
        category = category_result.scalar_one_or_none()
        if not category:
            raise ValueError(f"category_id {chapter_data.category_id}에 해당하는 카테고리를 찾을 수 없습니다.")

        job_result = await self.db.execute(select(Job).where(Job.job_id == category.job_id))
        job = job_result.scalar_one_or_none()
        if not job:
            raise ValueError("해당 카테고리에 연결된 직무(Job)가 존재하지 않습니다.")

        job_name = job.job_name
        job_description = job.description
        category_content = category.content
        
        prompt = f"""
        당신은 외국인 근로자에게 한국어를 가르치는 교육 설계자입니다.
        직무명: {job_name}
        직무 설명: {job_description}
        학습 카테고리: {category_content}
        난이도 단계(level_id): {chapter_data.level_id}

        이 학습 카테고리에 해당하는 '상황 기반 한국어 챕터'를 5개 제안하세요.
        각 챕터는 6개의 대표 문장을 포함해야 합니다.
        각 문장은 학습자가 실제 현장에서 사용할 수 있는 자연스러운 한국어 문장이어야 합니다.

        반드시 **유효한 JSON 형식**으로 출력하세요.
        문자열과 키는 모두 큰따옴표(")를 사용해야 합니다.
        JSON 배열만 출력하세요. 다른 텍스트는 포함하지 마세요.

        [
            {{
                "title": "주문 전화 받기",
                "description": "손님이 전화를 걸어 주문하는 상황을 다룹니다.",
                "sentences": [
                    "여보세요, 중국집입니다.",
                    "무엇을 주문하시겠어요?",
                    "주소를 알려주세요.",
                    "곧 배달해드릴게요.",
                    "감사합니다.",
                    "안녕히 계세요."
                ]
            }}
        ]
        """

        response = await self.llm_service.generate_text(prompt)
        raw = (response.get("content") or "").strip()

        if not raw:
            raise ValueError("LLM 응답이 비어 있습니다.")

        # 1) ```json 코드펜스 제거
        #   - 시작 펜스 제거: ```json\n
        #   - 끝 펜스 제거: \n```
        clean = re.sub(r"^```[a-zA-Z0-9_-]*\s*\n", "", raw)
        clean = re.sub(r"\n```$", "", clean)

        # 2) JSON 배열 본문만 슬라이스 (여분 문구/서문 방지)
        start = clean.find("[")
        end = clean.rfind("]")
        if start != -1 and end != -1:
            candidate = clean[start:end+1].strip()
        else:
            candidate = clean  # 혹시나 이미 순수 배열이면 그대로

        # 3) JSON → 실패 시 Python literal 파싱
        try:
            chapters_data = json.loads(candidate)
        except json.JSONDecodeError:
            try:
                chapters_data = ast.literal_eval(candidate)
            except Exception:
                # 디버그 용이하게 원문 일부만 보여줌
                preview = candidate[:500] + ("..." if len(candidate) > 500 else "")
                raise ValueError(f"LLM 응답이 JSON 형식이 아닙니다. 미리보기:\n{preview}")

        if not isinstance(chapters_data, list):
            raise ValueError(f"LLM 응답이 JSON 배열이 아닙니다: {type(chapters_data)}")
        
        created_chapters = []

        for i, ch in enumerate(chapters_data):
            if not isinstance(ch, dict):
                raise ValueError(f"{i+1}번째 항목이 객체가 아닙니다: {ch}")

            # title/description 정규화
            t = ch.get("title")
            if not isinstance(t, str) or not t.strip():
                raise ValueError(f"{i+1}번째 챕터에 유효한 title이 없습니다: {ch}")
            title = t.strip()

            d = ch.get("description")
            description = d.strip() if isinstance(d, str) else ""

            chapter = Chapter(
                category_id=chapter_data.category_id,
                level_id=chapter_data.level_id,
                title=title,
                description=description,
                is_active=True,
            )
            self.db.add(chapter)
            await self.db.flush()  # chapter_id 확보

            for sent_text in ch.get("sentences", []):
                if isinstance(sent_text, str) and sent_text.strip():
                    self.db.add(Sentence(
                        chapter_id=chapter.chapter_id,
                        content=sent_text.strip(),
                        translated_content=None,
                        tts_url=None,
                    ))

            created_chapters.append(chapter)

        await self.db.commit()

        return created_chapters

    async def update_chapter(self, chapter_id: int, chapter_update: ChapterUpdate) -> Optional[Chapter]:
        """챕터 수정"""
        chapter = await self.get_chapter_by_id(chapter_id)
        if not chapter:
            return None
        
        update_data = chapter_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(chapter, field, value)

        await self.db.commit()
        await self.db.refresh(chapter)
        
        return chapter
    
    async def delete_chapter(self, chapter_id: int) -> bool:
        """챕터 삭제 (소프트 삭제)"""
        chapter = await self.get_chapter_by_id(chapter_id)
        if not chapter.is_active:
            return False
        
        chapter.is_active = False
        await self.db.commit()
        
        return True
    

    async def get_chapter_sentences(
        self,
        chapter_id: int,
        page: int = 1,
        size: int = 20
    ) -> Tuple[List[Sentence], int]:
        """챕터 내 문장 목록 조회"""
        stmt = select(Sentence).where(Sentence.chapter_id == chapter_id)

        # 전체 개수
        count_stmt = select(func.count()).select_from(stmt.alias())
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar() or 0

        # 페이징
        stmt = stmt.offset((page - 1) * size).limit(size)
        result = await self.db.execute(stmt)
        sentences = list(result.scalars().all())

        return sentences, total
    
    # 특정 직무가 생성될 때 10개의 학습 카테고리 생성
    ## 카테고리 당 10개의 챕터 생성 -> level은 어떻게 고려?
    async def get_learning_categories(self, job_id: int) -> List[LearningCategory]:
        """학습 카테고리 조회"""
        result = await self.db.execute(
            select(LearningCategory).where(LearningCategory.job_id == job_id)
        )
        categories = list(result.scalars().all())

        if not categories:
            categories = await self.generate_learning_categories(job_id=job_id)

        return categories
    
    async def generate_learning_categories(self, job_id: int) -> List[LearningCategoryResponse]:
        """LLM을 활용한 학습 카테고리 생성"""
        job_result = await self.db.execute(select(Job).where(Job.job_id == job_id))
        job = job_result.scalar_one_or_none()

        if not job:
            return False
        
        job_name = job.job_name
        job_description = job.description

        prompt = f"""
            당신은 외국인 근로자에게 한국어를 가르치는 **교육 설계 전문가**입니다.

            다음 직무에 맞는 '상황 기반 한국어 학습 카테고리'를 설계하세요.

            직무명: {job_name}
            직무설명: {job_description}

            ---

            ### 목표
            이 직무를 수행하는 외국인 근로자가 **실제 현장에서 자주 겪는 상황 단위의 학습 카테고리**를 10개 제시하세요.

            각 카테고리는 다음을 만족해야 합니다:
            1. **실제 직무 환경의 구체적인 상황**이어야 합니다.  
            예: “손님에게 인사하기”, “고객 불만 응대하기”, “주문 전화 받기”
            2. **학습자가 사용할 수 있는 표현 학습이 가능한 주제**여야 합니다.
            3. **중복되거나 추상적인 표현(예: 서비스, 일상, 소통 등)**은 절대 피하세요.
            4. 각 항목은 **자연스러운 한국어 문장으로 된 100자 이내의 문장형 주제**로 작성하세요.
            5. **모든 출력은 JSON 배열 형식**으로만 작성하세요. JSON 이외의 설명 문장은 절대 포함하지 마세요.

            ---

            ### 출력 형식 (JSON 배열)
            출력은 아래와 같은 JSON 배열 형식으로 반환해야 합니다:

            [
                "손님에게 인사하기",
                "주문 요청 받기",
                "음식 전달하기",
                "결제 도와드리기",
                "식기 정리하기"
            ]

            ---

            ### 주의사항
            - 반드시 **JSON 배열 형식**만 출력하세요.
            - JSON 이외의 문장, 설명, 불릿포인트, 주석 등을 절대 포함하지 마세요.
            - 각 항목은 **문자열(String)** 형태여야 하며, JSON 배열 외의 문장은 절대 포함하지 마세요.
            """

        llm_result = await self.llm_service.generate_text(prompt)
        raw_content = llm_result["content"]

        try:
            category_contents = json.loads(raw_content)
            if not isinstance(category_contents, list):
                raise ValueError("JSON 배열 형식이 아닙니다.")
        except Exception:
            category_contents = [line.strip("[]\" ") for line in raw_content.split("\n") if line.strip()]

        categories = []
        for content in category_contents:
            category = LearningCategory(job_id=job_id, content=content)
            self.db.add(category)
            categories.append(category)

        await self.db.commit()
        for cat in categories:
            await self.db.refresh(cat)

        # ORM 객체를 Pydantic 모델로 변환하여 반환
        return [LearningCategoryResponse.model_validate(cat) for cat in categories]

