# 커뮤니티 서비스 가이드

## 목적
- 게시글과 댓글 관리

## 경로
- 엔드포인트: app/api/v1/endpoints/community.py
- 서비스: app/services/community_service.py
- 모델: app/models/community.py

## 개발 방법
- 게시글 목록: 카테고리, 정렬, 페이지네이션
- 게시글 작성/수정/삭제: 사용자 권한 검증, 소유자 일치 확인
- 댓글 CRUD: 게시글 기준 목록, 사용자 권한 검증

## 주의사항
- 조회수 증가는 동시성 고려 필요 시 DB 함수 또는 캐시 사용
- 카테고리 Enum 일치 검사
