# Essay vs prototype delta (Team OS borrow)

**날짜**: 2026-11-01  
**목적**: DeepSeek Harness 에세이 주장 7가지가 [공개 프로토타입](https://github.com/deepseek-ai/dsh-superagent-prototype)에 얼마나 들어 있는지 보고, Ork→Smith→Checker에 **무엇만** 가져올지 정한다. Router/Worker·Store·PR 계약은 [02](./02-dsh-superagent-borrow-notes.md) 참고 — 여기서는 중복 표 없음.

**이식 금지**: Feishu, SQLite Engine, DSH Harness 포트, 봇 헤드카운트 증가 (02 §3과 동일).

## Essay claim → prototype → Team OS

| Essay claim | in prototype? | Team OS action |
| --- | --- | --- |
| **Watchdog** — 메인 밖 주기적 Control Loop; infra 생존 + Worker 진행/드리프트 판단; 실행 중 자연어 개입 (§6) | **partial** — 별도 Watchdog Session 없음. `Passes`(주기 tick), Eval deadline, Report relay·slot·30분 백그라운드 한도 등 **운영 루프**는 있으나 에세이 수준의 외부 감시·교정 루프는 아님 | **adopt now** — DSH Watchdog 세션 대신 **Evening Close / Checker cadence**로 “transcript 밖 점검 + 기계적 증거” 패턴만 |
| **Speculative silent reproduce-fix** — 백그라운드 추측 재현·수정; 확정+단순 fix일 때만 말함 (§3.4) | **no** — 공개 docs에 동일 정책·모드 없음 (Worker는 Report taxonomy·Channel 규율로 “조용히 일하기”만 부분 유사) | **later** — Ork/Smith **observe** 정책 패턴으로만 연습; Checker 없이 auto-PR·silent merge는 **하지 않음** |
| **Channel bandwidth** — IM ≤100자·가벼운 인터럽트; GitHub/email 등 async는 구조화·밀도 높은 전달 (§4.2) | **partial** — ack **100 words** 상한([007 Architecture](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/main/docs/007-architecture.md)); Channel 목적별 writes·Outbox; Feishu/GitHub 채널 구현은 배포물 | **adopt now** — Slack/Ork↔Smith는 짧은 Attention; **Origin PR·리뷰**는 구조화 Report+링크로 dense surface |
| **Thread subscription + Fast Path** — Worker가 Thread 구독; 후속 Trigger는 코드 fan-out, Router tool 없음; Router는 미구독·신규만 (§3.2) | **yes** — [001 Domain](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/main/docs/001-domain.md) Subscription fan-out; follow-up ownership·handback ([003 Execution](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/main/docs/003-execution.md)) | **adopt now** — Ticket Assignment 후 follow-up **Smith 소유**; handback/stop 전 Ork 재라우팅 금지 (02 #3). fan-out 자동화는 **later** |
| **Chain of Recall / Inline & Spill** — ID 포인터, 최소 시작·인라인 요약·창 밖 full spill; board 상태는 transcript 밖 (§3.3) | **partial** — Engine+Store가 Trigger/Ticket/Input ID 보유; Worker prompt는 assignment·Trigger **card truncation**(1,500/600 chars) + Store에 full 기록 | **adopt now** — board/OPS에 Ticket·증거 포인터; chat에는 요약+링크만 (02 Store·Ticket 밖 상태) |
| **Async start/stop ReAct** — non-blocking start()/stop(); tool 결과는 이벤트 (§4.1) | **partial** — Harness 쪽 shell→background(5s/60s), job wake; 에세이 API와 동일한 ReAct start/stop 계약은 **Team OS 범위 밖** | **never** — Grok Bot/Harness 능력으로만 메모; Ork playground에서 구현·요구하지 않음 |
| **Security (credentials without model)** — 모델 비노출 credential; cloud+endpoint 신뢰 (§8.4) | **open-problem** — execution env에 credential 없음 명시, git credential helper 등 infra 힌트; 에세이 §8.4 수준 해결책은 공개 docs에 없음 | **later** — **플래그만** (vault/FillCredential 등 참고 메모 가능); DSH daemon·전용 credential proxy **never** |

## Pointers

- **Essay (X)**: https://x.com/DeepSeekHarness/status/2116857257245987236  
- **Prototype**: https://github.com/deepseek-ai/dsh-superagent-prototype  
- **Team OS borrow (02)**: [./02-dsh-superagent-borrow-notes.md](./02-dsh-superagent-borrow-notes.md)
