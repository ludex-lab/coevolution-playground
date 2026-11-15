# 실험 스케치: TokWatt × Cloud Agent 에너지 감각

**날짜**: 2026-10-31 · **유형**: 당일 체크리스트 (풀 스터디 아님)

## Goal

Ork 팀의 **Ork → Smith → Checker** 워크플로(및 Cursor **Cloud Agent** composer 런)에서, TokWatt가 정리한 **공개 추론 에너지 증거**를 이용해 **대략적인 Wh/run 또는 Wh/1M tokens** 숫자 하나를 말할 수 있게 한다. 목적은 정확한 계측이 아니라 **경계(boundary)·기능 단위(functional unit)·불확실성**을 함께 적는 usage awareness 습관을 만드는 것이다.

## Non-goals

- TokWatt 저장소 전체 클론, `build.py` 파이프라인 재현, 새 CSV 행 기여
- Cloud Agent 인프라의 실측 전력·PUE·GPU utilization
- Vercel/Ludex 배포, 비밀/API 키, 대규모 의존성 설치
- “우리 모델이 정확히 X Wh”처럼 단일 진실 주장 (참조 범위 + 가정을 반드시 병기)

## 역할 매핑 (Ork → Smith → Checker)

| 역할 | 이 스케치에서 할 일 |
|------|---------------------|
| **Ork** | 오늘 런의 functional unit 정의 (예: “coding-agent 세션 1회”, “PR 1건 위한 Cloud Agent 1 run”), TokWatt에서 쓸 task 라벨 선택, 기록 템플릿 확정 |
| **R** (필요 시) | arXiv 초록·TokWatt README·계산기 UI에서 boundary/참조값 의미 15분 읽기 |
| **Smith** | 대시보드/런 로그에서 **입력·출력 토큰 추정**, 계산기 또는 `task_defaults`/`token_factors`로 1차 Wh 산출 (스프레드시트 또는 아래 기록 블록) |
| **Checker** | 가정·boundary가 TokWatt harmonization(서버+시설)과 맞는지, 범위가 paper/README와 모순 없는지, “single-source task” 경고를 붙였는지 검증 |

## Inputs (전형적인 Cloud Agent 1 run)

아래는 **추정치**로 충분하다. 정확한 billing API가 없어도 스케치는 진행 가능하다.

| 입력 | 어디서 | 메모 |
|------|--------|------|
| Run ID / 대화 제목 | Cursor Cloud Agent 대시보드 | 재현용 링크만, 시크릿 없음 |
| 대략 모델 family | run 메타데이터 (예: composer-class agent) | TokWatt row와 1:1 대응 불필요 |
| **Input / output tokens** | usage 요약, diff 크기, 턴 수로 역산 | cache read는 unknown이면 TokWatt 한계로 명시 |
| Tool / subagent 호출 횟수 | transcript 이벤트 | “한 functional unit”에 포함할지 Ork가 먼저 정함 |
| Wall-clock | run 시작~종료 | Wh와 혼동 금지 (에너지 ≠ 시간) |

**TokWatt 쪽 고정 참고값 (v0.1.0, server+facility harmonized, README 요약)**

- Short chat answer: **0.34 Wh** (0.16–0.99)
- Reasoning answer: **4.7 Wh** (1.1–34)
- **One task delegated to an AI agent**: **150 Wh** (60–290, *n_sources=1*)
- **One coding-agent session**: **321 Wh** (41–1,200)

Cloud Agent PR 작업은 보통 **coding-agent session** 또는 **agent-delegated task**에 더 가깝다고 가정하고, chat-only 턴은 short chat/reasoning으로 쪼개도 된다.

## Steps (당일, 코드 최소)

### 1. Functional unit 고정 (Ork, ~10분)

- [ ] 오늘 run을 TokWatt **task** 중 하나로 이름 붙인다 (예: `coding_agent_session`, `agent_task`, `chat_reasoning`).
- [ ] “1 run = Cloud Agent가 사용자 follow-up 큐를 비울 때까지”처럼 **경계 문장**을 한 줄로 쓴다.

### 2. TokWatt 공개 계산기 (Smith, ~20분)

- [ ] [TokWatt calculator](https://araoufbh.github.io/tokwatt/)를 연다 (클론 불필요).
- [ ] 오늘 run에 맞는 **일일 사용 시나리오**를 rough count로 입력 (예: coding agent sessions ×1, reasoning answers ×N, short chats ×M).
- [ ] 화면의 **Wh central / range**, optional cost·CO₂e, “1 billion people” 스케일을 스크린샷 또는 숫자만 복사한다.
- [ ] 계산기가 쓰는 boundary가 **server + facility overhead**임을 README와 대조해 메모한다.

### 3. 토큰 기반 coarse estimate (선택, ~15분)

- [ ] TokWatt README의 `token_factors.csv` 설명을 읽고, **Wh per million input/output tokens** 계수가 있으면 run 토큰 추정치에 곱한다.
- [ ] cache-read 비율 불명이면 paper/README **Known limitations** 그대로 “±큰 unknown”을 기록한다.
- [ ] agent task **150 Wh** 또는 coding session **321 Wh**와 토큰 추정이 5× 이상 어긋나면, functional unit 정의를 다시 본다 (Ork).

### 4. DB만 빠르게 볼 때 (선택, 브라우저)

- [ ] GitHub `data/task_defaults.csv` 또는 `estimates.csv`를 **raw view**로 연다 ([repo](https://github.com/AraoufBh/tokwatt)).
- [ ] 선택한 task의 `n_sources`, `n_estimates`, central/range를 스케치 기록에 붙인다.

### 5. Checker pass (~10분)

- [ ] 숫자에 **단위(Wh)** 와 **범위**가 있는가?
- [ ] single-source task(150 Wh agent)를 “확정값”처럼 쓰지 않았는가?
- [ ] Cloud Agent run 토큰은 **추정**임을 표시했는가?

## What to record (한 run당)

```text
date: 2026-10-31
functional_unit: (한 문장)
tokwatt_task: (task id / 이름)
inputs: in_tokens ~, out_tokens ~, tool_turns ~, model_hint ~
method: calculator | task_default | token_factors | mixed
result_wh_central:
result_wh_range:
boundary_note: server+facility (TokWatt harmonized) | other
assumptions:
checker: pass | revise — (한 줄)
```

## Success criteria (스케치 완료)

- [ ] **하나의 Cloud Agent run**에 대해 **Wh/run** 또는 **Wh/1M tokens** 추정값 + **TokWatt 범위**가 기록됨
- [ ] Ork/Smith/Checker 역할이 기록에 반영됨 (누가 functional unit·검증을 했는지)
- [ ] boundary·single-source·토큰 추정 한계 중 **최소 2가지**가 assumptions에 명시됨
- [ ] “내일 풀 연구”가 아니라 **감각 calibration**이 목적임을 팀이 verbally 공유

## Next-day follow-up (2026-11-01 이후)

1. **두 번째 run** 같은 방법으로 반복해 Wh/run 분산이 functional unit 정의 때문인지 usage 때문인지 구분
2. TokWatt **reasoning vs coding-agent** ladder에서 우리 run이 어디쯤인지 1문단 회고
3. (선택) CONTRIBUTING 워크플로에 “실험 종료 시 Wh 메모 3줄”을 Ork 체크리스트에 넣을지 팀 결정 — 코드 변경은 별 PR
4. (선택) paper Section 8 calculator 시나리오를 팀 typical day와 맞춰 preset 이름만 문서화

## Evidence (오늘 채울 칸)

- Calculator / CSV 링크:
- 기록 블록 붙여넣기:
- Checker 한 줄:

## Status

- [x] Planning (스케치 작성)
- [ ] In Progress (당일 실행)
- [ ] Complete
- [ ] On Hold

**결론**: _(당일 실행 후 한 줄)_
