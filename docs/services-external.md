# 외부 연동 서비스 가이드

## 목적
- TTS, STT, LLM 외부 API 연동

## 경로
- 엔드포인트: app/api/v1/endpoints/external.py
- 서비스: app/services/external_service.py

## 개발 방법
- TTS: 텍스트 → 오디오 URL, 비동기 처리 고려
- STT: 업로드 파일 처리, 전송 포맷, 보관 정책
- LLM: 문장/챕터/시나리오 피드백 요청-응답 표준화

## 주의사항
- API 키 보안: .env와 비밀 관리
- 응답 지연 대비 타임아웃과 재시도 전략
