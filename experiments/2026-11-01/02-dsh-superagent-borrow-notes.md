# DeepSeek `dsh-superagent-prototype` — Team OS 차용 노트

**날짜**: 2026-11-01  
**목적**: MIT 연구 프로토타입의 Router/Worker·상태·허용·PR 계약을 Ork→Smith→Checker / board·OPS·handoff에 **개념만** 빌려올 항목을 정리한다. (하네스/Feishu/SQLite 이식·봇 증원·배포 없음.)

## 1) 요약: Router vs Worker, 상태 위치, allowlist/trigger, PR contract

DeepSeek [001 Domain](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/main/docs/001-domain.md) / [003 Execution](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/main/docs/003-execution.md) / [007 Architecture](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/main/docs/007-architecture.md) 기준 매핑.

| 역할 | dsh-superagent | 하는 일 |
|------|----------------|---------|
| **Router** | Main Session (`orchestrator`, preset `dsh-superagent-router`) | Eval의 gate + Policy 위에서 **Trigger를 받아 Ticket + Mandate를 만들거나** 라우팅. 사람이 행동해야 하거나 결과를 쓸 수 있을 때만 말함. |
| **Worker** | Executor Session (`worker-<ticket>`, preset `dsh-superagent-worker`) | Ticket당 **Assignment 하나 + 디렉터리 하나**. 구조화된 **Report** (`progress``/ `waiting` / `ready` / `blocked` / `failed``/ `dropped`)로 상태 보고, PR을 연다. |

**세션 밖의 상태**: `Engine` + SQLite **Store**가 Trigger / Thread / Ticket / Assignment / Mandate / Decision을 소유한다. Ticket 상태는 **채팅·DSH Session transcript를 따르지 않는다** (핸드오프·재개·Executor 교체 가능). Channel 쓰기·relay·launch 등 부수 효과는 **Outbox → Effects**로 커밋 후 내구 실행 ([007 Architecture](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/main/docs/007-architecture.md)).

**Allowlist / triggers**

- **Source** (GitHub, Feishu 등) → 불변 **Trigger** → **Thread**(시간순)로 기록.
- **Policy gate**: Source별 허용 목록(identity) + admission table + **accept mode** (`off` / `observe` / `auto`). Gate는 Eval 1층; Assessment는 모델 판단.
- **Mandate**: accept가 부여하는 **불변 권한** — scope, strength, matched rules, Policy version, 발신 identity. Ticket 종료만으로 Mandate가 사라지지 않음; **사람 stop** 또는 더 이상 Policy가 hold하지 않을 때만 철회.
- **Subscription**: Ticket↔Thread 다대다. 구독 Thread의 Trigger는 **Eval 없이 fan-out**되어 Executor에 맥락으로 전달; 사람 메시지가 Ticket에 도달하면 그 Ticket의 follow-up 소유권 유지.
- Eval은 **새 work를 시작할지**만 결정; 이미 Mandate로 살아 있는 Ticket의 연속 작업은 subscription으로 이어진다.

**PR contract** ([003 Execution](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/main/docs/003-execution.md))

- Ticket은 Executor가 보고한 PR 및 브랜치에서 연 PR을 **follow**한다.
- **완료(mechanical)**: Ticket이 **연 PR 중 열린 것이 없을 때** (merge/close) — transcript의 “끝냈다”가 아님.
- **Deliverable surface**: Channel writes — ack, reply, PR, attention — 가 외부에 보이는 결과면.
- **Auto-merge**는 Delivery requirements 프롬프트/별도 CLI 지시; Policy·Mandate와 분리.

## 2) Ork→Smith→Checker / board·OPS·handoff에 빌릴 3–5가지 (다음 버전 액션)

| # | dsh-superagent에서 | Ork playground에 적용 |
|---|-------------------|------------------------|
| 1 | Ticket + Mandate가 chat 밖 | **board/OPS**가 work-unit 상태(scope, strength, status)를 Ork/Smith transcript와 분리 보관. **Assignment** = Smith(Executor) 런 바인딩. |
| 2 | Report taxonomy | Smith→Ork 보고는 `ready` / `blocked` / `failed``/ `dropped` (+ 증거 링크) 고정; 자유형 “다 했어요” 금지. **Checker**는 그 분류에 대해 기계적 증거(Origin PR path, commit, diff)를 채점. |
| 3 | Follow-up ownership / handback | Ticket에 Assignment가 있으면 해당 Thread follow-up은 **소유 Worker(Smith)** 가 처리; scope 밖은 **handback** 후 Ork가 재라우팅. Ork 이중 오케스트레이션 축소 — **사람 stop** 또는 명시 handback 전에는 Ork가 다시 끼어들지 않음. |
| 4 | Done-when = forge evidence | 완료는 Origin PR URL·브랜치·커밋이 존재할 때(또는 paper-only + 명시 blocker). MANDATE checklist의 “Execution Misrepresentation” 기계적 standing rule과 정렬. |
| 5 | Attention = 구조화된 질문 하나 | board/OPS UI는 **사람 입력 대기(Attention)** 만 surface; 에이전트는 working 중 조용히 — Router가 “말할 때만 말하기”와 동일한 UX 규율. |

## 3) Do-not-borrow / overfit

DSH Harness·Feishu·SQLite Engine을 그대로 이식하거나 봇 헤드카운트를 늘리지 말 것 — Ork→Smith→Checker **계약을 먼저 깊게** 하고, auto-proactive 규칙은 **observe 모드**에서 충분히 본 뒤에만.

## 4) Pointers

| 항목 | 링크 |
|------|------|
| 저장소 (MIT) | https://github.com/deepseek-ai/dsh-superagent-prototype |
| 철학 | [docs/000-philosophy.md](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/main/docs/000-philosophy.md) |
| 도메인 | [docs/001-domain.md](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/main/docs/001-domain.md) |
| Authorization | [docs/002-authorization.md](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/main/docs/002-authorization.md) |
| Execution / PR 완료 | [docs/003-execution.md](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/main/docs/003-execution.md) |
| Architecture (Engine/Store/Outbox) | [docs/007-architecture.md](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/main/docs/007-architecture.md) |
| 공개 시그널 (LvWerra) | https://x.com/lvwerra/status/2116634303073321237 |

**오늘 실험 폴더와의 관계**

- **[01-mandate-agent-run-checklist.md](./01-mandate-agent-run-checklist.md)** — MANDATE 논문 렌즈로 Cloud Agent **런을 채점**하는 체크리스트 (PR [#4](https://cursor.com/codebase/coevolution-lab/playground/pull/4), 브랜치 `cursor/mandate-agent-run-checklist-f423`; main 병합 전이면 해당 PR에서 확인).
- **본 문서 (02)** — 외부 Team OS 프로토타입에서 **상태·handoff·PR 기계적 완료** 계약을 빌려오는 보조 노트. MANDATE는 “거짓 완료를 어떻게 잡을지”, DSH borrow는 “작업 단위를 transcript 밖에서 어떻게 굴릴지”를 짝으로 본다.
