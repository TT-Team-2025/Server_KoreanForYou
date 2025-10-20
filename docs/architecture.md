# 아키텍처

## 목표
- 유지보수성과 확장성을 위한 계층형 구조
- API와 비즈니스 로직, 데이터 접근의 관심사 분리

## 디렉토리 구조
- app/api: 라우팅과 요청/응답 처리
- app/services: 비즈니스 로직
- app/models: SQLAlchemy 모델
- app/schemas: Pydantic 스키마
- app/core: 설정, 보안, DB 연결
- alembic: 마이그레이션 스크립트

## 데이터베이스
- PostgreSQL 사용, SQLAlchemy 2.0 ORM
- Alembic으로 스키마 버전 관리

## 실행
- 로컬: python run.py
- Docker: docker-compose up -d

## 운영 고려사항
- 마이그레이션 자동화: 시작 스크립트에 alembic upgrade head 반영
- 로깅 표준화: JSON 로깅 도입 고려
- 시크릿: .env 및 Secret Manager 사용
