"""
시나리오 관련 API 엔드포인트
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.core.security import get_current_user_id, oauth2_scheme
from app.schemas.scenario import (
    ScenarioResponse, ScenarioCreate, ScenarioUpdate, ScenarioListResponse,
    ScenarioStartRequest, ConversationTurnRequest, ScenarioCompleteRequest,
    ScenarioProgressResponse, ScenarioFeedbackResponse
)
from app.schemas.common import BaseResponse
from app.services.scenario_service import ScenarioService

router = APIRouter()


@router.get("/", response_model=ScenarioListResponse)
async def get_scenarios(
    job_id: Optional[int] = Query(None, description="직무 ID"),
    level_id: Optional[int] = Query(None, description="레벨 ID"),
    page: int = Query(1, ge=1, description="페이지 번호"),
    size: int = Query(20, ge=1, le=100, description="페이지 크기"),
    db: Session = Depends(get_db)
):
    """시나리오 목록 조회"""
    scenario_service = ScenarioService(db)
    scenarios, total = scenario_service.get_scenarios(
        job_id=job_id,
        level_id=level_id,
        page=page,
        size=size
    )
    
    return ScenarioListResponse(
        scenarios=scenarios,
        total=total,
        page=page,
        size=size
    )


@router.get("/{scenario_id}", response_model=ScenarioResponse)
async def get_scenario(
    scenario_id: int,
    db: Session = Depends(get_db)
):
    """시나리오 상세 조회"""
    scenario_service = ScenarioService(db)
    scenario = scenario_service.get_scenario_by_id(scenario_id)
    
    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="시나리오를 찾을 수 없습니다"
        )
    
    return scenario


@router.post("/", response_model=BaseResponse)
async def create_scenario(
    scenario_data: ScenarioCreate,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """새 시나리오 등록 (관리자용)"""
    # TODO: 관리자 권한 확인 로직 추가
    scenario_service = ScenarioService(db)
    scenario = scenario_service.create_scenario(scenario_data)
    
    return BaseResponse(
        success=True,
        message="시나리오가 등록되었습니다",
        data={"scenario_id": scenario.scenario_id}
    )


@router.delete("/{scenario_id}", response_model=BaseResponse)
async def delete_scenario(
    scenario_id: int,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """시나리오 삭제 (관리자용)"""
    # TODO: 관리자 권한 확인 로직 추가
    scenario_service = ScenarioService(db)
    
    if not scenario_service.get_scenario_by_id(scenario_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="시나리오를 찾을 수 없습니다"
        )
    
    scenario_service.delete_scenario(scenario_id)
    
    return BaseResponse(
        success=True,
        message="시나리오가 삭제되었습니다"
    )


@router.post("/{scenario_id}/start", response_model=BaseResponse)
async def start_scenario(
    scenario_id: int,
    start_data: ScenarioStartRequest,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """시나리오 진행 시작 (로그 생성)"""
    user_id = get_current_user_id(token)
    scenario_service = ScenarioService(db)
    
    if not scenario_service.get_scenario_by_id(scenario_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="시나리오를 찾을 수 없습니다"
        )
    
    progress = scenario_service.start_scenario(user_id, scenario_id, start_data)
    
    return BaseResponse(
        success=True,
        message="시나리오가 시작되었습니다",
        data={"progress_id": progress.progress_id}
    )


@router.patch("/{scenario_id}/conversation", response_model=BaseResponse)
async def save_conversation_turn(
    scenario_id: int,
    conversation_data: ConversationTurnRequest,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """대화(turn) 기록 저장"""
    user_id = get_current_user_id(token)
    scenario_service = ScenarioService(db)
    
    scenario_service.save_conversation_turn(user_id, scenario_id, conversation_data)
    
    return BaseResponse(
        success=True,
        message="대화가 저장되었습니다"
    )


@router.patch("/{scenario_id}/complete", response_model=BaseResponse)
async def complete_scenario(
    scenario_id: int,
    complete_data: ScenarioCompleteRequest,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """시나리오 완료 처리"""
    user_id = get_current_user_id(token)
    scenario_service = ScenarioService(db)
    
    scenario_service.complete_scenario(user_id, scenario_id, complete_data)
    
    return BaseResponse(
        success=True,
        message="시나리오가 완료되었습니다"
    )


@router.get("/{scenario_id}/feedback", response_model=ScenarioFeedbackResponse)
async def get_scenario_feedback(
    scenario_id: int,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """시나리오 피드백 조회"""
    user_id = get_current_user_id(token)
    scenario_service = ScenarioService(db)
    
    feedback = scenario_service.get_scenario_feedback(user_id, scenario_id)
    
    if not feedback:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="시나리오 피드백을 찾을 수 없습니다"
        )
    
    return feedback


@router.post("/{scenario_id}/feedback", response_model=BaseResponse)
async def generate_scenario_feedback(
    scenario_id: int,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """AI 피드백 생성 요청"""
    user_id = get_current_user_id(token)
    scenario_service = ScenarioService(db)
    
    scenario_service.generate_scenario_feedback(user_id, scenario_id)
    
    return BaseResponse(
        success=True,
        message="AI 피드백 생성이 요청되었습니다"
    )
