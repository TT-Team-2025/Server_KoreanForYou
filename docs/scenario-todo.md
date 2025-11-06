# 시나리오 기능 추가 구현 사항

## 현재 구현된 기능 ✅

1. **POST /api/scenarios/start** - 시나리오 세션 시작
2. **POST /api/scenarios/message** - 텍스트 메시지 전송
3. **POST /api/scenarios/message/voice** - 음성 메시지 전송 (STT + LLM + TTS)
4. **POST /api/scenarios/end** - 시나리오 종료
5. **GET /api/scenarios/list** - 완료된 시나리오 목록 조회
6. **GET /api/scenarios/audio/{filename}** - TTS 오디오 파일 다운로드

---

## 추가 구현 필요 사항 📋

### 1. 진행 중인 시나리오 조회
**우선순위: 높음**

- **엔드포인트**: `GET /api/scenarios/progress/{thread_id}`
- **기능**: 특정 시나리오의 진행 상황 조회
- **응답 데이터**:
  - thread_id
  - scenario_title
  - user_role, ai_role
  - start_time
  - turn_count
  - completion_status
  - description
- **용도**: 클라이언트에서 진행 중인 시나리오 상태 확인

---

### 2. 대화 내역 조회
**우선순위: 높음**

- **엔드포인트**: `GET /api/scenarios/messages/{thread_id}`
- **기능**: 특정 시나리오의 전체 대화 내역 조회 (OpenAI Assistants API messages 활용)
- **응답 데이터**:
  - messages: List[Message]
    - role (user/assistant)
    - content
    - created_at
- **용도**: 
  - 완료된 시나리오 대화 내역 확인
  - 진행 중인 시나리오 대화 내역 확인
  - 대화 재개 시 이전 대화 확인

---

### 3. 시나리오 중단
**우선순위: 중간**

- **엔드포인트**: `POST /api/scenarios/cancel/{thread_id}`
- **기능**: 진행 중인 시나리오를 중단 상태로 변경
- **동작**:
  - completion_status를 CANCELLED로 변경
  - end_time 설정
- **용도**: 사용자가 시나리오를 중간에 포기할 때

---

### 4. 시나리오 재개
**우선순위: 중간**

- **엔드포인트**: `POST /api/scenarios/resume/{thread_id}`
- **기능**: 중단된 시나리오를 다시 시작
- **동작**:
  - completion_status를 IN_PROGRESS로 변경
  - end_time을 None으로 설정
- **용도**: 중단했던 시나리오를 다시 이어서 진행

---

### 5. 시나리오 피드백 생성
**우선순위: 중간**

- **엔드포인트**: `POST /api/scenarios/feedback/{progress_id}`
- **기능**: 완료된 시나리오에 대한 피드백 생성
- **요청 데이터**:
  - pronunciation_score (0-100)
  - accuracy_score (0-100)
  - fluency_score (0-100)
  - completeness_score (0-100)
  - comment (선택)
- **동작**:
  - ScenarioFeedback 레코드 생성
  - total_score 자동 계산
- **용도**: 사용자가 시나리오 완료 후 자신의 발화를 평가

---

### 6. 시나리오 피드백 조회
**우선순위: 낮음**

- **엔드포인트**: `GET /api/scenarios/feedback/{progress_id}`
- **기능**: 특정 시나리오의 피드백 조회
- **응답 데이터**: ScenarioFeedbackResponse
- **용도**: 이전에 작성한 피드백 확인

---

### 7. 진행 중인 시나리오 목록 조회
**우선순위: 중간**

- **엔드포인트**: `GET /api/scenarios/in-progress`
- **기능**: 현재 사용자의 진행 중인 시나리오 목록 조회
- **응답 데이터**: CompletedScenarioListResponse와 유사하지만 completion_status가 IN_PROGRESS
- **용도**: 사용자가 진행 중인 시나리오 목록 확인 및 재개

---

### 8. 사용자 시나리오 통계 조회
**우선순위: 낮음**

- **엔드포인트**: `GET /api/scenarios/stats`
- **기능**: 현재 사용자의 시나리오 학습 통계 조회
- **응답 데이터**:
  - total_scenarios: 전체 시나리오 수
  - completed_scenarios: 완료된 시나리오 수
  - in_progress_scenarios: 진행 중인 시나리오 수
  - cancelled_scenarios: 중단된 시나리오 수
  - total_turn_count: 전체 발화 횟수
  - average_turn_count: 평균 발화 횟수
  - average_feedback_score: 평균 피드백 점수 (있는 경우)
- **용도**: 사용자의 학습 진행 상황 대시보드

---

## 구현 순서 제안

### Phase 1 (필수 기능)
1. ✅ 진행 중인 시나리오 조회 (`GET /progress/{thread_id}`)
2. ✅ 대화 내역 조회 (`GET /messages/{thread_id}`)

### Phase 2 (편의 기능)
3. ✅ 진행 중인 시나리오 목록 조회 (`GET /in-progress`)
4. ✅ 시나리오 중단 (`POST /cancel/{thread_id}`)
5. ✅ 시나리오 재개 (`POST /resume/{thread_id}`)

### Phase 3 (피드백 기능)
6. ✅ 시나리오 피드백 생성 (`POST /feedback/{progress_id}`)
7. ✅ 시나리오 피드백 조회 (`GET /feedback/{progress_id}`)

### Phase 4 (통계 기능)
8. ✅ 사용자 시나리오 통계 조회 (`GET /stats`)

---

## 참고사항

- 모든 엔드포인트는 인증 필요 (`get_current_user` dependency 사용)
- `thread_id`는 OpenAI Thread ID를 의미
- `progress_id`는 `scenario_progress.progress_id`를 의미
- OpenAI Assistants API의 messages 엔드포인트 활용 시:
  - `GET /v1/threads/{thread_id}/messages`
  - `limit` 파라미터로 메시지 개수 제한 가능
  - `order` 파라미터로 정렬 순서 지정 가능 (asc/desc)


