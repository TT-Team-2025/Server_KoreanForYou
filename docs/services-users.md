# 사용자 서비스 가이드

## 목적
- 사용자 프로필 조회 및 업데이트

## 경로
- 코드: app/api/v1/endpoints/users.py
- 서비스: app/services/user_service.py
- 모델: app/models/user.py

## 개발 방법
- 내 정보 조회: 토큰에서 user_id 파싱 → DB 조회
- 전체 수정: Pydantic 스키마로 입력 검증 → 부분 업데이트 적용
- 비밀번호 변경: 현재 비밀번호 검증 → 새 비밀번호 해싱 저장
- 모국어/직무 변경: level_id, job_id 업데이트

## 주의사항
- 인증 의존성(oauth2_scheme) 누락 여부 점검
- 이메일, 비밀번호 정책 일관성 유지
