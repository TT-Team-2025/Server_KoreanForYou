# 인증 서비스 가이드

## 목적
- 회원가입, 로그인, 토큰 갱신, 로그아웃 제공

## 경로
- 코드: app/api/v1/endpoints/auth.py
- 서비스: app/services/user_service.py
- 스키마: app/schemas/user.py, app/schemas/common.py

## 개발 방법
- 회원가입: 이메일 중복 검사 → 비밀번호 해싱 → User, UserStatus 생성
- 로그인: 이메일 조회 → 비밀번호 검증 → Access/Refresh 토큰 발급
- 토큰 갱신: refresh 토큰 검증 → 새 토큰 발급
- 테스트: 이메일 포맷, 중복, 비밀번호 정책, 만료 시간

## 보안
- SECRET_KEY는 운영 환경에서 강한 랜덤값 사용
- 토큰 만료와 재발급 정책 관리
