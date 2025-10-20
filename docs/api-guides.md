# API 설계 가이드

## 기본 원칙
- RESTful 설계, 명확한 리소스 경로
- 버전 경로 미사용. 하위 호환성은 스키마 확장으로 해결
- 일관된 응답 구조(BaseResponse, 에러 응답)

## 인증
- JWT Bearer 토큰
- Authorization: Bearer <token>

## 에러 규약
- 4xx: 클라이언트 오류, 5xx: 서버 오류
- message와 details를 포함해 디버깅 용이성 확보

## 페이지네이션
- 쿼리 파라미터 page, size 사용
- 응답에 total, page, size 포함

## 문서화
- Swagger UI: /docs
- ReDoc: /redoc
