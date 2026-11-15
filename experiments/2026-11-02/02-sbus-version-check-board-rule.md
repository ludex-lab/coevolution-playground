# S-Bus-inspired version-check — Team OS board pointers & handbacks

**날짜**: 2026-11-02 · **유형**: 규칙 제안 (one-pager; broker 이식·Autopilot/Tincan/Slack/Ludex 변경 없음)  
**Paper**: [S-Bus: A Shared Data Broker for Multi-Agent Systems](https://arxiv.org/abs/2605.17076) (arXiv:2605.17076) · 선택적 공개 맥락: [triangle_chain thread](https://x.com/triangle_chain/status/2116960240981959154)

## 1) Problem — stale board pointers / handbacks

Ork→Smith→Checker에서 **board/OPS**와 handback 패킷은 transcript 밖 “진실”을 가리킨다: Chain-of-Recall **pointer ID**, forge **증거**(Origin PR head, commit SHA, diff 범위), mandate scope, Checker가 마지막으로 본 board row.

**실패 모드:** Smith가 작업을 **claim**한 뒤, Ork가 board를 갱신하거나 PR head가 force-push·rebase되거나, human이 같은 ticket에 새 지시를 올리면, Smith/Checker는 **옛 버전을 전제로** handback·완료 판정을 내린다. MANDATE 쪽 “Execution Misrepresentation”과 겹치지만, 여기서는 **감정이 아니라 기계적 stale-write**로 잡는다: “내가 의존했다고 선언한 아티팩트의 버전이 claim 이후 바뀌었는가?”

## 2) Borrow (S-Bus only) — not a port

**논문 아이디어 (축약):** 중앙 broker가 각 에이전트가 **어떤 데이터의 어떤 버전을 읽었는지** 기록하고, 쓰기 요청이 그 의존성과 충돌하면 **거부**(HTTP 409에 가까운 stale-write reject).

| 빌릴 것 | Team OS 번역 |
|--------|----------------|
| Read-set / version log | **Board pointer ID**별 **불변 version 토큰** (scoped `rev`, PR `headSha`, commit SHA 등) |
| Write with dependency | Handback·`ready` Report가 **`relied_on`** 목록을 선언 |
| Reject on conflict | Checker가 선언된 version ≠ 현재 board/forge면 **auto-return** (재작업·재claim) |

**명시적 non-port (오늘 범위 밖):** S-Bus **daemon**, SQLite store, Feishu relay, DSH Engine/Outbox, Slack bot, headcount 늘리기, Autopilot/Tincan. 규칙·체크리스트만 — 구현은 기존 board/Origin/수동 필드로 충분.

## 3) Proposed Team OS rule (board entries + handbacks)

**A. Board pointer row** (Ork 또는 board writer)

- **Canonical `id` = board pointer ID** (Origin PR number·repo path는 pointer가 가리키는 **version** 쪽 필드로만 기록).
- Pointer마다 **`rev`** (단조 증가)와 **`artifacts[]`**: `{ id, kind, version }` — 여기서 `id`는 항상 board pointer ID.
- `kind` 예: `board_row`, `origin_pr`, `commit`, `cor_doc`, `mandate`.
- `version` 예: scoped `rev`, PR head SHA, commit SHA, 문서 git SHA.
- **Human/external edit:** 전 board `rev`를 매번 올리지 않음 — **변경된 scoped field**(mandate scope, blocker, PR follow 등)에 해당하는 pointer/field만 bump.

**B. Claim** (Smith가 턴 시작)

- Claim 패킷에 **`read_set`**: claim 시점에 읽은 `{ id, version }[]` (pointer ID + 그 시점 version).

**C. Handback / Smith→Ork Report (`ready` | `blocked` | …)**

- 필수 필드: **`relied_on`**: `[{ id, version }, …]` — **이번 handback·판단에 실제로 쓴** pointer/증거만 (claim `read_set`의 **부분집합**으로 충분; read_set 전체 dump **강제하지 않음**). DSH Report taxonomy와 동일하게 자유 서술 금지.

**D. Stale-write reject (기계적; rollout §4)**

- Handback 제출 시: ∀ entry ∈ `relied_on`, **현재 board/forge의 `(pointer id → version)`** 와 equality 비교.
- **Hard-enforce 단계**에서 mismatch → **accept 금지**; Checker는 `stale_write_reject`로 Smith에 반환 (Ork 재라우팅). “transcript에서 설명으로 덮기”는 standing rule 위반.

**E. Ork 재개**

- Ork는 bump된 `rev`/새 head를 board에 반영한 뒤 Smith **재claim** (`read_set` 갱신).

## 4) How Checker enforces (mechanical checklist)

Checker는 vibe가 아니라 아래 순서만 실행한다. **Rollout (Jihoon):** **1–2 handback cycle**은 mismatch를 **observe/log만** (`would_stale_reject`, `stale_ids[]`); 그 다음 cycle부터 **hard `stale_write_reject`**.

1. **Handback schema:** `relied_on` 존재·비어 있지 않음 (`ready`일 때). `blocked`/`failed`는 blocker pointer만 최소 1개. 각 `id`는 **board pointer ID**; `relied_on` ⊆ claim `read_set` 권장이나 **read_set 전체 제출 강제 없음** — decision에 쓴 것만 completeness 대상.
2. **Forge-evidence done gate:** `ready` + `kind: origin_pr` 항목이 있으면 URL·branch·**head SHA**가 `relied_on`과 일치하고 PR이 열려 있거나 merge 정책과 일치.
3. **Version diff:** board snapshot(또는 live read)으로 각 pointer **`id`의 current version** 조회 → mismatch 목록 작성 (scoped field bump만 반영된 rev/hash).
4. **Verdict taxonomy:**  
   - all match → Checker 독립 검증(diff/CI) 계속.  
   - any mismatch → **observe phase:** log only, handback may proceed if other gates pass. **Hard phase:** **`stale_write_reject`** (Report `failed` 또는 handback return); Smith는 갱신된 `read_set`으로 재claim 후만 재제출.
5. **State-outside-transcript:** 거부(또는 would-reject) 이유는 board/OPS row에 **`reject_reason: stale_dependency`** (또는 `would_stale_reject`), `stale_ids[]`로 남김 — chat 요약만으로는 완료 처리 금지.
6. **Handback ownership:** stale reject 후 follow-up은 **동일 Smith Assignment** (DSH borrow #3과 정렬) 또는 명시 handback; Ork는 재claim 전 중복 지시 금지.

## 5) Do-not-cite / Decided (Jihoon)

**Do-not-cite:** arXiv:2605.17076의 **거부된 요청 수**(예: 논문/스레드에 나오는 590/639→0/638류 숫자)는 **stale-write가 얼마나 자주 발생했는지**를 보여줄 뿐, **최종 산출물 품질·정확도 증명이 아니다**. Team OS KPI로 “reject 0건”을 성공으로 판매하지 않는다.

**Decided (Jihoon)** — 더 이상 open question 아님.

| # | 결정 |
|---|------|
| 1 | Canonical artifact **`id` = board pointer ID** |
| 2 | Human/external edits → **`rev` bump는 scoped fields만** (whole-board 매번 bump 아님) |
| 3 | Handback **`relied_on` = decision에 쓴 전부**; claim `read_set`의 부분집합으로 충분 — **read_set full dump 강제 안 함** |
| 4 | **Observe/log 1–2 cycles** → 이후 **hard `stale_write_reject`** (§4 rollout) |

**Merge hygiene:** Who Takes #1은 [PR #6](https://cursor.com/codebase/coevolution-lab/playground/pull/6)로 먼저 merge하고, [PR #7](https://cursor.com/codebase/coevolution-lab/playground/pull/7)은 그 **후** merge (또는 #6 merge 후 main에 rebase) — #7만 merge하면 #1이 side effect로 섞이지 않도록.

---

**오늘 폴더와의 관계:** [01-who-takes-the-lead-handoff-checklist.md](./01-who-takes-the-lead-handoff-checklist.md)는 **누가 턴을 가져갈지(Δ·handoff)**; 본 문서(02)는 **턴을 가진 뒤 어떤 board 버전에 쓸 수 있는지(stale-write reject)**. Ork→Smith→Checker를 새 역할 없이 깊게 한다.
