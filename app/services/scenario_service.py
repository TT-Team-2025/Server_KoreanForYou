"""
시나리오 관련 서비스
"""
from sqlalchemy.orm import Session
from typing import Optional, List, Tuple
from datetime import datetime

from app.models.scenario import Scenario, Role, ScenarioProgress, ScenarioFeedback
from app.schemas.scenario import (
    ScenarioCreate, ScenarioUpdate, ScenarioStartRequest, 
    ConversationTurnRequest, ScenarioCompleteRequest
)


class ScenarioService:
    def __init__(self, db: Session):
        self.db = db
    
    def get_scenarios(
        self, 
        job_id: Optional[int] = None, 
        level_id: Optional[int] = None,
        page: int = 1, 
        size: int = 20
    ) -> Tuple[List[Scenario], int]:
        """시나리오 목록 조회"""
        query = self.db.query(Scenario)
        
        if job_id is not None:
            query = query.filter(Scenario.job_id == job_id)
        
        if level_id is not None:
            query = query.filter(Scenario.level_id == level_id)
        
        total = query.count()
        scenarios = query.offset((page - 1) * size).limit(size).all()
        
        return scenarios, total
    
    def get_scenario_by_id(self, scenario_id: int) -> Optional[Scenario]:
        """ID로 시나리오 조회"""
        return self.db.query(Scenario).filter(Scenario.scenario_id == scenario_id).first()
    
    def create_scenario(self, scenario_data: ScenarioCreate) -> Scenario:
        """시나리오 생성"""
        scenario = Scenario(**scenario_data.dict())
        
        self.db.add(scenario)
        self.db.commit()
        self.db.refresh(scenario)
        
        return scenario
    
    def update_scenario(self, scenario_id: int, scenario_update: ScenarioUpdate) -> Optional[Scenario]:
        """시나리오 수정"""
        scenario = self.get_scenario_by_id(scenario_id)
        if not scenario:
            return None
        
        update_data = scenario_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(scenario, field, value)
        
        self.db.commit()
        self.db.refresh(scenario)
        
        return scenario
    
    def delete_scenario(self, scenario_id: int) -> bool:
        """시나리오 삭제"""
        scenario = self.get_scenario_by_id(scenario_id)
        if not scenario:
            return False
        
        self.db.delete(scenario)
        self.db.commit()
        
        return True
    
    def start_scenario(
        self, 
        user_id: int, 
        scenario_id: int, 
        start_data: ScenarioStartRequest
    ) -> ScenarioProgress:
        """시나리오 시작"""
        progress = ScenarioProgress(
            user_id=user_id,
            scenario_id=scenario_id,
            user_role_id=start_data.user_role_id,
            ai_role_id=start_data.ai_role_id,
            description=start_data.description,
            conversation=[],
            start_time=datetime.utcnow(),
            completion_status="진행중"
        )
        
        self.db.add(progress)
        self.db.commit()
        self.db.refresh(progress)
        
        return progress
    
    def save_conversation_turn(
        self, 
        user_id: int, 
        scenario_id: int, 
        conversation_data: ConversationTurnRequest
    ) -> bool:
        """대화 턴 저장"""
        progress = self.db.query(ScenarioProgress).filter(
            ScenarioProgress.user_id == user_id,
            ScenarioProgress.scenario_id == scenario_id,
            ScenarioProgress.completion_status == "진행중"
        ).first()
        
        if not progress:
            return False
        
        # 대화 내역에 추가
        if not progress.conversation:
            progress.conversation = []
        
        progress.conversation.append({
            "turn_number": conversation_data.turn_number,
            "user_message": conversation_data.user_message,
            "ai_response": conversation_data.ai_response,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        progress.turn_count = conversation_data.turn_number
        
        self.db.commit()
        
        return True
    
    def complete_scenario(
        self, 
        user_id: int, 
        scenario_id: int, 
        complete_data: ScenarioCompleteRequest
    ) -> bool:
        """시나리오 완료"""
        progress = self.db.query(ScenarioProgress).filter(
            ScenarioProgress.user_id == user_id,
            ScenarioProgress.scenario_id == scenario_id,
            ScenarioProgress.completion_status == "진행중"
        ).first()
        
        if not progress:
            return False
        
        progress.conversation = complete_data.final_conversation
        progress.completion_status = "완료"
        progress.end_time = datetime.utcnow()
        
        self.db.commit()
        
        return True
    
    def get_scenario_feedback(self, user_id: int, scenario_id: int) -> Optional[ScenarioFeedback]:
        """시나리오 피드백 조회"""
        progress = self.db.query(ScenarioProgress).filter(
            ScenarioProgress.user_id == user_id,
            ScenarioProgress.scenario_id == scenario_id
        ).first()
        
        if not progress:
            return None
        
        return self.db.query(ScenarioFeedback).filter(
            ScenarioFeedback.log_id == progress.progress_id
        ).first()
    
    def generate_scenario_feedback(self, user_id: int, scenario_id: int) -> bool:
        """AI 피드백 생성 요청"""
        # TODO: 실제 AI 서비스 연동 구현
        # 현재는 기본 피드백 생성
        progress = self.db.query(ScenarioProgress).filter(
            ScenarioProgress.user_id == user_id,
            ScenarioProgress.scenario_id == scenario_id
        ).first()
        
        if not progress:
            return False
        
        # 기본 피드백 생성
        feedback = ScenarioFeedback(
            user_id=user_id,
            log_id=progress.progress_id,
            pronunciation_score=85,
            accuracy_score=90,
            fluency_score=80,
            completeness_score=88,
            total_score=86,
            comment="전반적으로 잘하셨습니다. 발음을 조금 더 명확하게 하시면 좋겠습니다.",
            detail_comment=[
                "발음: 'ㅅ'과 'ㅆ' 구분을 더 명확하게 해주세요",
                "유창성: 문장을 더 자연스럽게 연결해보세요",
                "완성도: 대화의 맥락을 더 잘 파악해보세요"
            ]
        )
        
        self.db.add(feedback)
        self.db.commit()
        
        return True
    
    def get_roles(self) -> List[Role]:
        """모든 역할 조회"""
        return self.db.query(Role).all()
    
    def create_role(self, role_name: str, description: Optional[str] = None) -> Role:
        """역할 생성"""
        role = Role(role_name=role_name, description=description)
        
        self.db.add(role)
        self.db.commit()
        self.db.refresh(role)
        
        return role
