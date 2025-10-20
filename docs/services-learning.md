# 학습 콘텐츠 서비스 가이드

## 목적
- 챕터, 문장, 유사 문장 관리

## 경로
- 엔드포인트: app/api/v1/endpoints/chapters.py, sentences.py
- 서비스: app/services/chapter_service.py, sentence_service.py
- 모델: app/models/learning.py

## 개발 방법
- 챕터 목록: job_id, level_id 필터, 페이지네이션
- 챕터 생성/수정/삭제: 관리자 권한 체크 후 처리
- 문장 조회/수정/삭제: 문장 단위 CRUD 제공
- 유사 문장: sentence_id 기반 다건 조회

## 주의사항
- 삭제는 소프트 삭제(챕터) 또는 하드 삭제(문장) 정책 준수
- 타 도메인(진행, 피드백)과의 관계 무결성 유지
