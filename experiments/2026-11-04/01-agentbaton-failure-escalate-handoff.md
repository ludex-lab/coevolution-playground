# AgentBaton-style failure escalate — Team OS handoff checklist

**날짜**: 2026-11-04  
**Paper**: [AgentBaton: Efficient Model Collaboration in Agentic Tasks](https://arxiv.org/abs/2610.35959) ([NVIDIA Lab](https://research.nvidia.com/labs/lpr/agentbaton/))

## Paper citation only (not today’s protocol)

AgentBaton은 장기 에이전트 태스크에서 **한 번의 잘 맞춘 모델 핸드오프**로 비용·정확도 트레이드오프를 연구한다. 공개 요약은 11개 모델 쌍·두 벤치마크에서 **평균 API 비용 ~65.9% 절감**을 보고한다 ([2610.35959](https://arxiv.org/abs/2610.35959), [Lab page](https://research.nvidia.com/labs/lpr/agentbaton/)).  
**오늘 playground는 그 수치를 재현하지 않는다.** 아래는 Team OS용 **실패 반복 → 더 강한 모델** 에스컬레이션 스케치이며, 논문의 capable→efficient 방향과 **반대 방향**이다. 빌려오는 것은 “워크스페이스 + 로그로 컨텍스트 이전” 아이디어([Lab: context transfer](https://research.nvidia.com/labs/lpr/agentbaton/))뿐이다.

---

## Core fields

| Field | Definition |
|-------|------------|
| `failure-id` | 안정적인 실패 시그니처. 예: CI job + exit class, linter rule id, 동일 assertion 메시지 해시, 동일 tool error code. **의도·잡음이 아닌 재현 가능한 실패**만 카운트. |
| `consecutive_fail_count` | **같은 `failure-id`가 연속으로** 증가하는 카운터. 다른 `failure-id`로 바뀌면 **0으로 리셋** 후 새 id에서 1부터. |
| `escalate_when` | `consecutive_fail_count >= 2` (동일 실패 **두 번 연속**). |
| `handoff_artifact` | 수신(더 강한) 모델이 받는 **기계적 패킷** — 아래 두 항목만 필수. **NOT** full chat transcript dump. |

### `handoff_artifact` (required)

1. **`workspace_pointer`** — 리포 루트·브랜치·head SHA, (있다면) 작업 디렉터리 상대 경로; 에이전트가 이미 만든 파일 diff는 git state로 보면 됨.
2. **`log_path`** — 실패 재현에 필요한 **실행 로그 파일 경로** (예: CI log, test runner stdout 파일, `npm test` tee). 로그는 **증거**; narrative transcript는 넣지 않음.

선택(짧게): `failure-id`, `consecutive_fail_count`, `escalate_when` 트리거 시각, 이전 모델 tier 이름.

---

## Procedure (Ork → stronger model)

1. **Detect** — 각 실패 턴 끝에 `failure-id`를 계산·기록한다.
2. **Count** — 직전 턴과 `failure-id`가 같으면 `consecutive_fail_count += 1`, 다르면 새 id로 리셋 후 `= 1`.
3. **Escalate** — `escalate_when`이 true이면:
   - 현재 (약한/기본) 모델 런 **중단**;
   - `handoff_artifact`만 조립해 **더 강한 모델** 세션을 연다;
   - 강한 모델은 **워크스페이스 + `log_path` 내용**으로 상태를 복원하고, 같은 목표로 계속한다 (새 시도부터; transcript 재주입 없음).
4. **Checker** — 에스컬레이션 후 첫 성공 시 `failure-id` 카운터 클리어; 동일 id가 또 2연속이면 tier 정책(사람/다른 playbook)은 **별도 결정** (오늘 범위 밖).

---

## Worked example row (**example** — fictional, plausible)

| label | task ticket | failure-id | consecutive_fail_count | escalate_when | handoff_artifact |
|-------|-------------|------------|------------------------|---------------|-------------------|
| **example** | `TEAMOS-8842` — fix flaky `integration/api` on branch `cursor/payments-retry-5cee` | `pytest::tests/integration/api/test_webhook.py::test_retry_429::AssertionError: expected 2 calls got 1` | 2 | true (≥2 same) | `workspace_pointer`: repo `playground`, branch `cursor/payments-retry-5cee`, SHA `a1b2c3d`; `log_path`: `/tmp/ci-TEAMOS-8842-run3.log` |

강한 모델이 받는 것: 위 포인터로 checkout된 트리 + `log_path` 파일. **받지 않는 것**: Slack/IDE 전체 대화 transcript.

---

## Out of scope (2026-11-04)

- AgentBaton **설치·학습·detector** 배포
- **새 봇** 또는 Ork routine 편집
- Slack 연동
- 다른 PR / `experiments/2026-11-03/` Copilot trajectories **수정**
- DSH / Feishu / SQLite / daemon / headcount ports
- 논문·NVIDIA 페이지 **벤치마크 재실행** (~65.9% 등 수치 검증)

---

## Status

- [x] Planning (checklist sketch)
- [ ] In Progress (no runtime wiring)
- [ ] Complete

**Next step:** Checker가 merge gate에서 `handoff_artifact`에 transcript가 없는지 확인; 런타임 정책은 별도 PR.
