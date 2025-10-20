# 시나리오 서비스 가이드

## 목적
- 대화 시나리오 작성, 진행, 완료, 피드백

## 경로
- 엔드포인트: app/api/v1/endpoints/scenarios.py
- 서비스: app/services/scenario_service.py
- 모델: app/models/scenario.py

## 개발 방법
- 목록/상세: job_id, level_id 필터 조회
- 시작: ScenarioProgress 생성, 상태 진행중
- 대화 기록: turn 기반 대화 append
- 완료: 대화 마무리, 상태 완료, end_time 설정
- 피드백: 로그 기반 ScenarioFeedback 생성/조회

## 주의사항
- 상태 전이(진행중 → 완료) 일관성 유지
- 역할(Role) 참조 무결성 확인
