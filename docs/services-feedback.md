# 피드백 서비스 가이드

## 목적
- 챕터, 문장, 시나리오 피드백 저장 및 조회

## 경로
- 엔드포인트: app/api/v1/endpoints/feedback.py
- 서비스: app/services/feedback_service.py
- 모델: app/models/learning.py, app/models/scenario.py

## 개발 방법
- 챕터 피드백: upsert 방식 저장
- 문장 피드백: upsert 방식 저장
- 시나리오 피드백: 최근 진행(progress) 기준 조회

## 주의사항
- JSON 필드 스키마 일관성 유지
- 사용자/리소스 매칭 검증
