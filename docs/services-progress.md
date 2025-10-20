# 학습 진행 서비스 가이드

## 목적
- 사용자 진행률과 문장 단위 진행 관리

## 경로
- 엔드포인트: app/api/v1/endpoints/progress.py
- 서비스: app/services/progress_service.py
- 모델: app/models/progress.py, app/models/learning.py

## 개발 방법
- 사용자 진행 현황: 챕터/문장 합산 통계 계산
- 챕터 진행 갱신: UserProgress upsert, last_access_at 갱신
- 문장 진행 갱신: SentenceProgress upsert
- 이력 조회: UserProgress 기반 정리

## 주의사항
- Decimal 타입 진행률 계산 시 정밀도 주의
- 시간 필드 업데이트 표준화
