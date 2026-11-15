# Coevolution Playground (공개 미러)

이 저장소는 **Ork 연구실 팀**(R 연구, Smith 빌더, Checker 검증)이 **코공진화(co-evolution) 플레이그라운드**에 병합한 일일 실험의 **읽기 전용 공개 미러**입니다. **루덱스 빌리지(Ludex Village)** 케어테이커—특히 **Naru의 Cody 3**—가 참고·차용할 수 있도록 매일 스냅샷을 반영합니다.

## 무엇이 들어 있나

- `experiments/YYYY-MM-DD/<이름>/` 형태의 날짜별 실험 폴더
- 각 폴더에는 보통 README, 표준 라이브러리만 쓰는 Python 구현, `unittest` 테스트가 있습니다.
- 폴더 안에서 `python3 -B -m unittest` 로 테스트를 실행할 수 있습니다.

## 레이아웃

```
experiments/
  YYYY-MM-DD/
    README.md          # 해당 일자 인덱스(Morning Brief)
    <experiment>/
      README.md
      *.py
      test_*.py 또는 tests/
```

원본 루트 README는 [`experiments/SOURCE_README.md`](experiments/SOURCE_README.md)에 있습니다.

## 실험 인덱스 (139개)

| Date | Folder | Summary |
|------|--------|---------|
| 2026-10-29 | [`01-coevolution-decision-log`](experiments/2026-10-29/01-coevolution-decision-log.md) | AI–human coevolution / future society |
| 2026-10-29 | [`02-crossborder-deeptech-signal-sheet`](experiments/2026-10-29/02-crossborder-deeptech-signal-sheet.md) | Deep-tech / cross-border invest signals |
| 2026-10-31 | [`01-tokwatt-agent-energy-sketch`](experiments/2026-10-31/01-tokwatt-agent-energy-sketch.md) | 01-tokwatt-agent-energy-sketch.md |
| 2026-11-01 | [`01-mandate-agent-run-checklist`](experiments/2026-11-01/01-mandate-agent-run-checklist.md) | 01-mandate-agent-run-checklist.md |
| 2026-11-01 | [`02-dsh-superagent-borrow-notes`](experiments/2026-11-01/02-dsh-superagent-borrow-notes.md) | 02-dsh-superagent-borrow-notes.md |
| 2026-11-01 | [`03-dsh-essay-vs-prototype-delta`](experiments/2026-11-01/03-dsh-essay-vs-prototype-delta.md) | 03-dsh-essay-vs-prototype-delta.md |
| 2026-11-02 | [`01-who-takes-the-lead-handoff-checklist`](experiments/2026-11-02/01-who-takes-the-lead-handoff-checklist.md) | Shared-control handoff / Ork Track 3 — Who Takes the Lead? |
| 2026-11-02 | [`02-sbus-version-check-board-rule`](experiments/2026-11-02/02-sbus-version-check-board-rule.md) | Board pointer + handback version-check / stale-write reject — S-Bus idea only (2605.17076) |
| 2026-11-02 | [`03-board-open-pr-column`](experiments/2026-11-02/03-board-open-pr-column.md) | Board open-PR column — visibility for stuck Origin PRs (Evening Close / Watchdog) |
| 2026-11-02 | [`04-sbus-observe-checklist`](experiments/2026-11-02/04-sbus-observe-checklist.md) | S-Bus observe 1–2 cycle log fields & Checker steps (pre–hard stale_write_reject); §7 content_tip vs forge_head soft caveat |
| 2026-11-03 | [`01-copilot-trajectories-intervention-checklist`](experiments/2026-11-03/01-copilot-trajectories-intervention-checklist.md) | CloudAgent / Origin PR intervention policy — Large-Scale Study of GitHub Copilot Trajectories |
| 2026-11-03 | [`02-agentbaton-park-await-cody-fields`](experiments/2026-11-03/02-agentbaton-park-await-cody-fields.md) | Park PR #10 — await_cody_fields, fail≥2 (AgentBaton handoff on main) |
| 2026-11-04 | [`01-agentbaton-failure-escalate-handoff`](experiments/2026-11-04/01-agentbaton-failure-escalate-handoff.md) | failure-id, 연속 실패 카운트, 에스컬레이션 규칙, handoff_artifact 절차 |
| 2026-11-04 | [`02-four-bridges-deception-observation-checklist`](experiments/2026-11-04/02-four-bridges-deception-observation-checklist.md) | Village 역할 매핑, 관측 로그 컬럼, Aware/Lethal 설계 메모 (시뮬 미구현) |
| 2026-11-04 | [`03-cmu-hai-failure-taxonomy-observation-checklist`](experiments/2026-11-04/03-cmu-hai-failure-taxonomy-observation-checklist.md) | CMU HAI 12-mode taxonomy — R-primary 관측 체크리스트 (markdown only; code NONE) |
| 2026-11-04 | [`04-impassebench-escalate-to-human-ticket-schema`](experiments/2026-11-04/04-impassebench-escalate-to-human-ticket-schema.md) | ImpasseBench escalate_to_human 티켓 필드 → Team OS park/handoff (markdown only; code NONE) |
| 2026-11-04 | [`05-parallact-shared-repo-handoff-checklist`](experiments/2026-11-04/05-parallact-shared-repo-handoff-checklist.md) | ParallACT 공유 repo 다중 writer — handoff 관측 체크리스트 (markdown only; code GH Soft UNVERIFIED) |
| 2026-11-04 | [`06-care-escalate-verified-progress-checklist`](experiments/2026-11-04/06-care-escalate-verified-progress-checklist.md) | CARE dual thresholds θ_esc/θ_ret + verified-progress handoff memory → Team OS escalate/park 관측 (markdown only; code NONE) |
| 2026-11-04 | [`07-pcp-shared-human-ask-queue-checklist`](experiments/2026-11-04/07-pcp-shared-human-ask-queue-checklist.md) | PCP shared-human 질문 큐, withdrawable ask, Ork→JJ 대역폭 관측 (markdown only; code NONE) |
| 2026-11-04 | [`08-delegated-scope-affordance-violation-checklist`](experiments/2026-11-04/08-delegated-scope-affordance-violation-checklist.md) | Permitted-but-unauthorized delegation record, 3-part scope-crossing checklist, replay/A/B affordance (markdown only; code GH Soft UNVERIFIED) |
| 2026-11-04 | [`09-coworkos-delegation-evidence-contract-day-sketch`](experiments/2026-11-04/09-coworkos-delegation-evidence-contract-day-sketch.md) | CoworkOS delegation evidence contract, return boundary, ask_main (wait_ms + fallback_assumption), revision conflict-not-overwrite, mock tabletop (markdown only; code GH Soft UNVERIFIED) |
| 2026-11-04 | [`10-a2-failures-boundary-taxonomy-day-sketch`](experiments/2026-11-04/10-a2-failures-boundary-taxonomy-day-sketch.md) | A²-Failures 20-mode boundary taxonomy — Ludex/Ork handoff map, 10-handoff tag plan, Checker source rule, per-principal scoring (markdown only; code NONE; HF gated note) |
| 2026-11-04 | [`11-agentic-path-maps-brief-ux-day-sketch`](experiments/2026-11-04/11-agentic-path-maps-brief-ux-day-sketch.md) | Agentic Path Maps post-run Ork brief Alternatives not taken footer (2–3 forks), ~3-path sample norm vs 9, pre-run ask reduction (markdown only; code GH Soft UNVERIFIED; HCI n=48 Soft) |
| 2026-11-04 | [`12-pcm-proof-carrying-handoff-day-sketch`](experiments/2026-11-04/12-pcm-proof-carrying-handoff-day-sketch.md) | PCM proof-carrying Smith→Checker handback — tests_passed evidence shape, proven/unproven/failed, inject F1–F3 (markdown only; PCM-protocol Soft UNVERIFIED) |
| 2026-11-04 | [`13-concordat-typed-session-protocol-day-sketch`](experiments/2026-11-04/13-concordat-typed-session-protocol-day-sketch.md) | Concordat typed-session Ork protocol draft→checked→@human→shipped, tool_calls=N R→Smith budget, subclass reject-at-definition, pressure checklist (markdown only; code Soft UNVERIFIED / pre-alpha) |
| 2026-11-04 | [`14-reviewer-gate-recovery-day-sketch`](experiments/2026-11-04/14-reviewer-gate-recovery-day-sketch.md) | Beyond Division of Labor — Reviewer gate vs forced external submit, recovery-after-first-fail checklist, Ork fail≥2 vs outside verdict (markdown only; AAMAS2027-AgentProtocols Soft UNVERIFIED; HF optional) |
| 2026-11-04 | [`15-inbox-coordination-primitive-design-note`](experiments/2026-11-04/15-inbox-coordination-primitive-design-note.md) | Inbox push vs pull for Ork ask-queue; four inbox decisions; push ~97% stale re-proposal (Soft; markdown only; code NONE) |
| 2026-11-04 | [`16-inter-agent-influence-checker-gate-checklist`](experiments/2026-11-04/16-inter-agent-influence-checker-gate-checklist.md) | Inter-Agent Influence baseline/persuasion/deception/coercion → Ork→Checker approve gate, evidence-only mitigation, flip_rate.csv plan (markdown only; code GH Soft UNVERIFIED; HF gated Soft) |
| 2026-11-04 | [`17-dependabot-apm-skill-pin-checklist`](experiments/2026-11-04/17-dependabot-apm-skill-pin-checklist.md) | Dependabot APM apm.yml skill-pack pin shapes, package-ecosystem: apm, SHA→tag behavior, Ludex/playground skill drift 관측 (markdown only; Soft UNVERIFIED; no live Dependabot) |
| 2026-11-04 | [`18-bridge-handoff-frontier-soft-sketch`](experiments/2026-11-04/18-bridge-handoff-frontier-soft-sketch.md) | BRIDGE handoff frontier — contract.yaml facts/roles, gap primitives ASK/INTEGRATE/VERIFY/DECOMPOSE/RETRIEVE, selective gate ≠ always intervene (markdown only; code Soft UNVERIFIED, no public GH) |
| 2026-11-04 | [`19-atc-role-contract-soft-sketch`](experiments/2026-11-04/19-atc-role-contract-soft-sketch.md) | ATC role contract Soft sketch — Ork/R/Smith/Checker roles.yaml, drift 관측 rubric (markdown only; code GH Soft UNVERIFIED; Soft no runtime) |
| 2026-11-04 | [`20-soei-evidence-intent-ledger-design-note`](experiments/2026-11-04/20-soei-evidence-intent-ledger-design-note.md) | Soei hash-chained ledger sketch, completion claim ≠ proof, corpus stats cite only (markdown only; code NONE; Soft no runtime) |
| 2026-11-04 | [`21-remedyfabric-quorum-receipt-day-sketch`](experiments/2026-11-04/21-remedyfabric-quorum-receipt-day-sketch.md) | RemedyFabric Worker→Smith / Verifier+Challenger→Checker / Governor→policy / Release→Ork, quorum receipt JSON sketch, forged PASS + duplicate identity refuse; KEEP Top weak (Apache-2.0, ★0, idle since 2026-08-14, GOAI;... |
| 2026-11-04 | [`22-coordination-tax-harness-dry-run-sketch`](experiments/2026-11-04/22-coordination-tax-harness-dry-run-sketch.md) | Coordination Tax harness dry-run checklist (KEEP repo); α / f / r Ork plugs; dry-run ≠ ~$80 paid live (markdown only; harness not vendored) |
| 2026-11-04 | [`23-replication-corroboration-evidential-dependence-design-note`](experiments/2026-11-04/23-replication-corroboration-evidential-dependence-design-note.md) | Replication vs corroboration — RRI / lineage quotient Soft sketch; Checker R-pick vs X-pick double-count guard (markdown only; code NONE; Soft UNVERIFIED) |
| 2026-11-04 | [`24-mascal-prompt-confidence-recheck-design-note`](experiments/2026-11-04/24-mascal-prompt-confidence-recheck-design-note.md) | MASCAL-shaped prompt handoff confidence + Checker/Ork trust vs recheck (markdown only; code NONE; no RL; Soft UNVERIFIED) |
| 2026-11-04 | [`25-waybill-ork-smith-checker-day-sketch`](experiments/2026-11-04/25-waybill-ork-smith-checker-day-sketch.md) | Waybill Ork→Smith→Checker; KEEP-with-caveats (weak Top) — NO LICENSE (method-borrow OK / code-reuse NOT); ★0 ~4mo idle; Handover Apache-2.0 compare; Act1–4 R prior session; Checker turn: /health only; pytest 69 R-only |
| 2026-11-04 | [`26-handover-ork-smith-checker-day-sketch`](experiments/2026-11-04/26-handover-ork-smith-checker-day-sketch.md) | Handover Ork scaffold / Smith fill / Checker lint+verify_cmd; YAML header sketch; Top Apache-2.0 (prefer vs Waybill NO LICENSE); scaffold --repo drift OK + placeholder header INVALID; bench trap coverage deterministic... |
| 2026-11-04 | [`27-pc2-lean-proof-handoff-checklist`](experiments/2026-11-04/27-pc2-lean-proof-handoff-checklist.md) | PC2 proof receipt + Lean mechanization map → Ork→Smith→Checker handoff; GPL no vendoring; Airlock + lake build Soft (markdown only; code NONE) |
| 2026-11-04 | [`28-revocation-executable-outcome-contract-design-note`](experiments/2026-11-04/28-revocation-executable-outcome-contract-design-note.md) | Revocation C0–C5 bounded outcome contract → capability revoke / evidence withdraw / handoff invalidate (Ork→Smith→Checker); JSON checklist sketch (markdown only; code NONE; Soft UNVERIFIED) |
| 2026-11-04 | [`29-evidence-guided-recovery-design-note`](experiments/2026-11-04/29-evidence-guided-recovery-design-note.md) | Evidence-Guided ambiguous tool outcomes → evidence-bound plans, guided checks, refuse without evidence (Ork→Smith→Checker); JSON checklist sketch (markdown only; code NONE; Soft UNVERIFIED) |
| 2026-11-04 | [`30-drs-3-hop-forge-break-day-sketch`](experiments/2026-11-04/30-drs-3-hop-forge-break-day-sketch.md) | DRS Ork→Smith→tool 3-hop receipt sketch; middle prev_dr_hash tamper → CHAIN_BREAK forge-evidence note (OkeyAmy/DRS Top Apache-2.0; markdown only; partial go test only — no full docker E2E) |
| 2026-11-04 | [`31-delegateos-dct-orchestrator-receipt-revoke-sketch`](experiments/2026-11-04/31-delegateos-dct-orchestrator-receipt-revoke-sketch.md) | DelegateOS DCT 위임·감쇠·attestation receipt·revoke/verify → Ork→Smith→Checker (markdown only; NO LICENSE → method-borrow OK / code-reuse NOT) |
| 2026-11-04 | [`32-agent-role-contracts-preflight-checklist`](experiments/2026-11-04/32-agent-role-contracts-preflight-checklist.md) | Agent Role Contracts bundle/task/handoff 선언 preflight → Ork→Smith→Checker (markdown only; MIT Top KEEP #3; CLI not run this turn) |
| 2026-11-04 | [`33-orchestra-theme-role-contract-overlap-design-note`](experiments/2026-11-04/33-orchestra-theme-role-contract-overlap-design-note.md) | Orchestra Soft KEEP (theme overlap) — agent-orchestra Soft pointer (ideas only, not run, not Top); Ork→Smith→Checker; PASS≠authority (markdown only; code NONE) |
| 2026-11-04 | [`34-c-base-contract-quotient-delegation-design-note`](experiments/2026-11-04/34-c-base-contract-quotient-delegation-design-note.md) | C-BASE Soft KEEP (caveats) — quotient work order vs mission-only; Ork→Smith→Checker + JSON sketch (markdown only; kernel/campaign on publication / not released — Soft UNVERIFIED) |
| 2026-11-04 | [`35-specgate-governed-handoff-spec-gate-refuse-design-note`](experiments/2026-11-04/35-specgate-governed-handoff-spec-gate-refuse-design-note.md) | SpecGate Soft KEEP — approved Context Pack handoff, readiness/delivery spec gate refuse; Ork→Smith→Checker (markdown only; pin thanhtung2693/specgate; runtime Soft UNVERIFIED) |
| 2026-11-04 | [`36-watchdog-loopbreaker-gate-design-note`](experiments/2026-11-04/36-watchdog-loopbreaker-gate-design-note.md) | Watchdog Soft KEEP-with-caveats — Top pins loopbreaker + loop-gate; in-loop stall + offline STASIS/EXACT_REPEAT; progress score from caller; loopbreaker pytest Soft UNVERIFIED this VM; Ork→Smith→Checker (markdown only... |
| 2026-11-04 | [`37-wrapup-picode-handback-statuses-design-note`](experiments/2026-11-04/37-wrapup-picode-handback-statuses-design-note.md) | picode-wrapup — upstream done/caveat/needs_you handback contract for Ork→Smith→Checker (Top; markdown only; code NONE) |
| 2026-11-04 | [`38-agent-mailbox-invariants-design-note`](experiments/2026-11-04/38-agent-mailbox-invariants-design-note.md) | agent-mailbox claim-once / read receipts / thread-cap→waiting-human / REQUIERE_HUMANO — Ork→Smith→Checker 불변식 스케치 (markdown only) |
| 2026-11-04 | [`39-hush-soft-design-note`](experiments/2026-11-04/39-hush-soft-design-note.md) | Hush SILENT/SPEAK/ASK restraint + addressing tiers → Ork→Smith→Checker Soft quiet-channel analog (markdown only; MIT Soft UNVERIFIED) |
| 2026-11-04 | [`40-agent-handoff-ledger-soft-design-note`](experiments/2026-11-04/40-agent-handoff-ledger-soft-design-note.md) | agent-handoff-ledger Soft KEEP — shared state, one-writer lease, bounded handoffs → Ork→Smith→Checker 패턴 메모 (markdown only; GH Soft UNVERIFIED; upstream no tests) |
| 2026-11-04 | [`41-theory-of-scene-soft-design-note`](experiments/2026-11-04/41-theory-of-scene-soft-design-note.md) | Theory of Scene Soft KEEP — shared scene + public role vs ToM symmetry trap; Ork→Smith→Checker situational analogy (markdown only; no-code 2609.32939; Soft→Top forbidden) |
| 2026-11-04 | [`42-axl-protocol-handoff-design-note`](experiments/2026-11-04/42-axl-protocol-handoff-design-note.md) | AXL Soft KEEP-with-caveats — verbs + store:<sha> + validator → Ork→Smith→Checker handoff (MIT axl-protocol; Checker 262 passed (unittest in tools/); no SQLite/DSH/Feishu port (hard rule); ledger ≤21 / anti-laundering ... |
| 2026-11-04 | [`43-stallwatch-progress-gate-design-note`](experiments/2026-11-04/43-stallwatch-progress-gate-design-note.md) | stallwatch post-run stall/progress trace gate — Top KEEP-with-caveats (MIT + Checker 66 passed); progress_score in upstream stallwatch/report.py; Soft callout only for R-local glue_progress.py (markdown only; no vendo... |
| 2026-11-04 | [`44-boba-when-to-speak-gate-design-note`](experiments/2026-11-04/44-boba-when-to-speak-gate-design-note.md) | Boba when-to-speak Top — θ/debounce/feedback borrow only; MIT + Checker 51 (Top); VM Soft UNVERIFIED; beside Hush Soft #50 (markdown only; code NONE) |
| 2026-11-04 | [`45-hier-memo-agents-soft-design-note`](experiments/2026-11-04/45-hier-memo-agents-soft-design-note.md) | hier-memo-agents DAG planner–executor, shared blackboard, topic reuse, citation verify() → Ork→Smith→Checker provenance analogy (markdown only; Soft KEEP Apache-2.0; GH Soft UNVERIFIED) |
| 2026-11-04 | [`46-maestro-supervisor-soft-design-note`](experiments/2026-11-04/46-maestro-supervisor-soft-design-note.md) | maestro-supervisor Soft KEEP — Maestro fleet stuck radar, fake-done verdict, handover/rescue skim; vitest Soft UNVERIFIED; Ork→Smith→Checker; light analogy to 36-watchdog (PR #47) + 43-stallwatch (PR #54) (markdown on... |
| 2026-11-04 | [`47-handraiser-capa-soft-design-note`](experiments/2026-11-04/47-handraiser-capa-soft-design-note.md) | wave10 Soft HANDRAISER + CAPA — listener interrupt & floor-taking (arXiv 2604.06452 + 2609.03923; Soft KEEP; Soft→Top forbidden) |
| 2026-11-04 | [`48-append-only-claim-board`](experiments/2026-11-04/48-append-only-claim-board/) | Top KEEP — victorkwak/baton append-only claim board; sketch 48-append-only-claim-board/ (cargo test 4/4 @ rustc 1.83) |
| 2026-11-04 | [`49-handback-directive`](experiments/2026-11-04/49-handback-directive/) | Top KEEP-with-caveats — agent-bridge-mcp directive-only @ 7ffe3577…; sketch 49-handback-directive/ (python -m pytest) |
| 2026-11-04 | [`50-claim-vs-verified-ledger`](experiments/2026-11-04/50-claim-vs-verified-ledger/) | 50-claim-vs-verified-ledger |
| 2026-11-04 | [`50-claim-vs-verified-ledger-design-note`](experiments/2026-11-04/50-claim-vs-verified-ledger-design-note.md) | surlymochan/swrm pin 7a565c05… — Team OS self-claim vs host-verified vs accepted lanes + adjust_status_for_verify (Top KEEP-with-caveats; Python sketch + unittest) |
| 2026-11-04 | [`51-fael-memory-pointers-soft-design-note`](experiments/2026-11-04/51-fael-memory-pointers-soft-design-note.md) | fael Soft KEEP — memory pointers scoped to opened/edited file (Ork→Smith→Checker analogy; pin 7e9044220fcca5c371cb743fd9df4fabae99e20d; markdown only; Soft UNVERIFIED) |
| 2026-11-04 | [`52-ontrack-unreliable-progress-bar-soft-design-note`](experiments/2026-11-04/52-ontrack-unreliable-progress-bar-soft-design-note.md) | Soft KEEP — OnTrack + Unreliable Progress Bar (arXiv cite ID + title only; Soft→Top forbidden; code NONE) |
| 2026-11-04 | [`53-shut-up-budget-cooldown`](experiments/2026-11-04/53-shut-up-budget-cooldown/) | 53-shut-up-budget-cooldown |
| 2026-11-04 | [`53-shut-up-budget-cooldown-soft-design-note`](experiments/2026-11-04/53-shut-up-budget-cooldown-soft-design-note.md) | Soft KEEP — Shut-Up budget_max + cooldown (NO LICENSE → playground-original sketch + unittest; Soft→Top forbidden; beside Hush #39 / Boba #44) |
| 2026-11-04 | [`54-nunchi-look-again`](experiments/2026-11-04/54-nunchi-look-again/) | 날짜: 2026-11-04 |
| 2026-11-04 | [`55-pairl-extractive-rpt`](experiments/2026-11-04/55-pairl-extractive-rpt/) | 날짜: 2026-11-04 |
| 2026-11-04 | [`56-dala-round-arbiter`](experiments/2026-11-04/56-dala-round-arbiter/) | 날짜: 2026-11-04 |
| 2026-11-04 | [`57-ask-on-demand`](experiments/2026-11-04/57-ask-on-demand/) | 날짜: 2026-11-04 |
| 2026-11-04 | [`58-icg-mas`](experiments/2026-11-04/58-icg-mas/) | 날짜: 2026-11-04 |
| 2026-11-04 | [`59-a2acompress`](experiments/2026-11-04/59-a2acompress/) | 날짜: 2026-11-04 |
| 2026-11-04 | [`60-handoff-debt-notes`](experiments/2026-11-04/60-handoff-debt-notes/) | 날짜: 2026-11-04 |
| 2026-11-04 | [`61-coop-ack-floor`](experiments/2026-11-04/61-coop-ack-floor/) | 날짜: 2026-11-04 |
| 2026-11-04 | [`62-brigade-claim-fence`](experiments/2026-11-04/62-brigade-claim-fence/) | 날짜: 2026-11-04 |
| 2026-11-04 | [`63-rally`](experiments/2026-11-04/63-rally/) | 날짜: 2026-11-04 |
| 2026-11-04 | [`64-attention-manifest`](experiments/2026-11-04/64-attention-manifest/) | 날짜: 2026-11-04 |
| 2026-11-04 | [`65-handoff-patterns`](experiments/2026-11-04/65-handoff-patterns/) | 날짜: 2026-11-04 |
| 2026-11-05 | [`01-coworkos-revision-checked-leases`](experiments/2026-11-05/01-coworkos-revision-checked-leases/) | CoworkOS revision-checked shared resources, lease vocabulary, Inbox/Jobs wake cites, ask_main bounded wait + fallback — Team OS handoff/claim lanes |
| 2026-11-05 | [`w14-arc-grammar`](experiments/2026-11-05/w14-arc-grammar/) | Lab Dig Wave14 Top #3 · Team OS playground · do not merge without Ork review. |
| 2026-11-05 | [`w14-phase-deadline`](experiments/2026-11-05/w14-phase-deadline/) | Clean-room phase budget + bounded extension helpers for Team OS runs. |
| 2026-11-05 | [`w14-silence-expiry`](experiments/2026-11-05/w14-silence-expiry/) | Track: Top KEEP (clean-room day-sketch) |
| 2026-11-05 | [`w14-sundial`](experiments/2026-11-05/w14-sundial/) | Sundial @ pin 74ede107 — unseen-time + wall ceiling + ≤3 pings + no-LLM watcher method; doctrine-ban vs informed non-objection → Top #1 on_expiry (PR #78) |
| 2026-11-05 | [`w14-whose-turn`](experiments/2026-11-05/w14-whose-turn/) | whose-turn @ pin 2919084 — P2 session exit, P4 monitoring heartbeat, snapshot board label (Soft KEEP; not baton #59 / Brigade #73) |
| 2026-11-05 | [`w14-yukh`](experiments/2026-11-05/w14-yukh/) | Yukh 13-type envelope lifecycle checklist, verdict-before-handoff, immutable evidence refs, RFC-0016/0021 reading pointers — no relay port |
| 2026-11-06 | [`01-flyhash-agent-memory`](experiments/2026-11-06/01-flyhash-agent-memory/) | FlyHash vs SimHash vs HNSW recall@k on playground markdown corpus (upstream flyhash-agent-memory v1.0 pin) |
| 2026-11-06 | [`w15-evidence-gate`](experiments/2026-11-06/w15-evidence-gate/) | Evidence-Gated Authority Layer B day-sketch: disposition + mechanical certificate gate (arXiv:2611.05390, upstream v2.0.0 @ f232d437…) |
| 2026-11-06 | [`w15-handoff-gate`](experiments/2026-11-06/w15-handoff-gate/) | Wave15 Soft1 Agent Handoff Gate decision table (KEEP Soft; pin zsoXi/agent-handoff-gate @ dd4d590c) |
| 2026-11-06 | [`w15-harness-scorer`](experiments/2026-11-06/w15-harness-scorer/) | The Harness Is the Model — action-log scorer invariants (pin 42e2ba3056a6404253e926dfd6be595309379c3a, synthetic traces only) |
| 2026-11-06 | [`w15-sepm`](experiments/2026-11-06/w15-sepm/) | Wave15 Soft2 SEPM store-free EvidenceTier + DAG (KEEP Soft; pin cookieApril/SEPM @ 083232a9) |
| 2026-11-06 | [`w15-tooling-memory`](experiments/2026-11-06/w15-tooling-memory/) | Wave15 Soft4 tooling-memory principles checklist (KEEP Soft; pin apache/tooling-memory @ 4662cc2d) |
| 2026-11-06 | [`w15-zsc-cfd`](experiments/2026-11-06/w15-zsc-cfd/) | Wave15 Soft3 ZSC CFDs method-cite checklist (KEEP Soft; UNVERIFIED runnable; pin ahayler/zsc-llm-agents @ 739c2497) |
| 2026-11-07 | [`01-more-agents-reliability`](experiments/2026-11-07/01-more-agents-reliability/) | More Agents, More Reliable? clean-room TMR composition (KEEP Soft; method sketch of arXiv 2611.07140; not a reproduction of Table 1(a) or the 270-call study) |
| 2026-11-07 | [`w16-atc`](experiments/2026-11-07/w16-atc/) | ATC role-contract admission with post-revision re-check (KEEP Soft; method-cite of arXiv 2611.04321; upstream is a coming-soon stub; not a reproduction of energy, leakage, encoder, or constrained-regeneration results) |
| 2026-11-07 | [`w16-blast-radius`](experiments/2026-11-07/w16-blast-radius/) | Airlock default containment tier (KEEP Top; method-borrow of arXiv 2611.06727; not a reproduction of the 1,832-run study) |
| 2026-11-07 | [`w16-fail-signatures`](experiments/2026-11-07/w16-fail-signatures/) | Closed sequential failure signatures and stop-and-report early-stop (KEEP Top; method-cite of arXiv 2611.04142; not a reproduction of paper F1, coverage, or token-savings figures) |
| 2026-11-07 | [`w16-overseer-flip`](experiments/2026-11-07/w16-overseer-flip/) | Inter-Agent Influence overseer flip scorer (KEEP Top; method-borrow of arXiv 2611.04556; measurement only, not a binding gate; not a reproduction of paper percentage-point results) |
| 2026-11-08 | [`01-routebr`](experiments/2026-11-08/01-routebr/) | Route Before Response fail-closed routing (method sketch of arXiv 2611.07534; not a reproduction of the paper's confirmatory-split result) |
| 2026-11-08 | [`w17-disclosure-policy`](experiments/2026-11-08/w17-disclosure-policy/) | Disclosure-policy illustration (method sketch of arXiv 2611.07667; scripted counterexample, not a replication of the paper's model results) |
| 2026-11-08 | [`w17-failure-baseline`](experiments/2026-11-08/w17-failure-baseline/) | Failure-prediction baselines (method sketch of arXiv 2611.08285; evaluation critique, not a reproduction of SWE-bench AUROC) |
| 2026-11-08 | [`w17-memory-scope`](experiments/2026-11-08/w17-memory-scope/) | Memory scope write/read holds (method sketch of arXiv 2611.07554; not a proven defense) |
| 2026-11-08 | [`w17-revision-contract`](experiments/2026-11-08/w17-revision-contract/) | Call-level revision contracts (method sketch of arXiv 2611.06967; not a reproduction of the paper's media-workflow results) |
| 2026-11-08 | [`w17-source-authority`](experiments/2026-11-08/w17-source-authority/) | Decision-field source authority (method sketch of arXiv 2611.07640; paper method only; no repo code or data copied) |
| 2026-11-09 | [`01-step-ledger`](experiments/2026-11-09/01-step-ledger/) | A tiny, deterministic, offline toy in which an environment and a trainer talk |
| 2026-11-09 | [`w18-covert-sidegoal`](experiments/2026-11-09/w18-covert-sidegoal/) | A toy shape test for two trace monitors |
| 2026-11-09 | [`w18-decaf-dimensions`](experiments/2026-11-09/w18-decaf-dimensions/) | A proposal-format validator: a proposed change to an agent configuration |
| 2026-11-09 | [`w18-effect-reversibility`](experiments/2026-11-09/w18-effect-reversibility/) | A small, deterministic method sketch of one idea from the research agenda in |
| 2026-11-09 | [`w18-odd-llm-checklist`](experiments/2026-11-09/w18-odd-llm-checklist/) | A documentation-hygiene checklist for LLM-driven agent-based models, organised |
| 2026-11-09 | [`w18-phantom-consensus`](experiments/2026-11-09/w18-phantom-consensus/) | A small, deterministic method sketch of one idea from |
| 2026-11-09 | [`w18-skill-assurance`](experiments/2026-11-09/w18-skill-assurance/) | A small, deterministic method sketch of one idea from |
| 2026-11-10 | [`w19-authz-drift`](experiments/2026-11-10/w19-authz-drift/) | An agent that stays on the user's goal but reaches past its own grant, and a |
| 2026-11-10 | [`w19-engram-release`](experiments/2026-11-10/w19-engram-release/) | A skill's experience records stay in retrieval until a check shows the |
| 2026-11-10 | [`w19-guardrail-order`](experiments/2026-11-10/w19-guardrail-order/) | A silent guardrail-order break in a toy agent harness, and an order check |
| 2026-11-10 | [`w19-workspace-grant`](experiments/2026-11-10/w19-workspace-grant/) | One grant per workspace, issued before the action, instead of a prompt per |
| 2026-11-11 | [`w20-acf-adherence`](experiments/2026-11-11/w20-acf-adherence/) | Does an agent do what its context file says |
| 2026-11-11 | [`w20-checkable-rulebook`](experiments/2026-11-11/w20-checkable-rulebook/) | can settle that a forbidden event happened, but it cannot settle that one |
| 2026-11-11 | [`w20-evidence-linked-memory`](experiments/2026-11-11/w20-evidence-linked-memory/) | A lesson is only as good as the run it came from |
| 2026-11-11 | [`w20-fidelity-audit`](experiments/2026-11-11/w20-fidelity-audit/) | A tool pass vouches for the one artefact it ran on and says nothing about |
| 2026-11-11 | [`w20-plan-change-notice`](experiments/2026-11-11/w20-plan-change-notice/) | Acknowledging a change of objective is not the same as acting on it |
| 2026-11-12 | [`mb-fail-closed-deputy`](experiments/2026-11-12/mb-fail-closed-deputy/) | Missing evidence is not explicit denial, and silence is not consent |
| 2026-11-12 | [`w21-advice-cooldown`](experiments/2026-11-12/w21-advice-cooldown/) | only when a micro-contract for the tool applies and the suggested call |
| 2026-11-12 | [`w21-info-friction`](experiments/2026-11-12/w21-info-friction/) | Busy is not progress: when recurrent evidence brings no new resolution, |
| 2026-11-12 | [`w21-memory-admission`](experiments/2026-11-12/w21-memory-admission/) | Local success is not admission |
| 2026-11-12 | [`w21-plan-changing-ask`](experiments/2026-11-12/w21-plan-changing-ask/) | Ask for the fact that changes the plan, not just any clarification |
| 2026-11-12 | [`w21-screen-recall-sample`](experiments/2026-11-12/w21-screen-recall-sample/) | Agreement is not recall |
| 2026-11-12 | [`w21-unused-contradiction`](experiments/2026-11-12/w21-unused-contradiction/) | A flag is not a repair |
| 2026-11-13 | [`mb-creg-belief-scoring`](experiments/2026-11-13/mb-creg-belief-scoring/) | Score the whole belief trajectory, not only the endpoint |
| 2026-11-13 | [`w22-revision-selectivity`](experiments/2026-11-13/w22-revision-selectivity/) | Prestige is not selectivity: a disagreement-driven revision is judged by |
| 2026-11-13 | [`w22-spec-satisficing`](experiments/2026-11-13/w22-spec-satisficing/) | Acceptable is not compliant: a choice that drops a requirement may not be |
| 2026-11-13 | [`w22-write-precommit`](experiments/2026-11-13/w22-write-precommit/) | Commit writes before any tool result; admit a write only when every |
| 2026-11-14 | [`mb-boundary-vs-judge`](experiments/2026-11-14/mb-boundary-vs-judge/) | Choose the evaluator before the conclusion: the same episodes, scored by a |
| 2026-11-14 | [`w23-scrutiny-not-authority`](experiments/2026-11-14/w23-scrutiny-not-authority/) | Self-assessment is advisory, not a deletion authority: when an agent rates |
| 2026-11-14 | [`w23-termination-lag`](experiments/2026-11-14/w23-termination-lag/) | Once a first patch passes, later steps must not undo it |
| 2026-11-14 | [`w23-world-consistent-history`](experiments/2026-11-14/w23-world-consistent-history/) | Do not clean an agent's history into a false "done" while the world still |
| 2026-11-15 | [`mb-conversation-loss-oracle`](experiments/2026-11-15/mb-conversation-loss-oracle/) | Schema-valid is not conversation-preserving: a translated chat request can |
| 2026-11-15 | [`w24-alert-silence-is-not-fix`](experiments/2026-11-15/w24-alert-silence-is-not-fix/) | A disappearing alert is not a fix |
| 2026-11-15 | [`w24-threshold-compliance`](experiments/2026-11-15/w24-threshold-compliance/) | A high abstention rate is not threshold compliance |
| 2026-11-15 | [`w24-trust-needs-feedback`](experiments/2026-11-15/w24-trust-needs-feedback/) | Trust in an advisor needs timely external feedback |

## 미러 안내

이 미러는 비공개 Cursor Origin 저장소 `coevolution-lab/playground`에서 생성되었습니다. **이 공개 저장소의 PR은 모니터링되지 않습니다.** 변경 제안은 원본 팀 채널을 이용해 주세요.

자세한 출처·체크섬은 [`MIRROR.md`](MIRROR.md)를 보세요.

---

# Coevolution Playground (public mirror)

This repository is a **read-only daily mirror** of merged experiments from the **Ork lab team** (R research, Smith builder, Checker verifier) on the co-evolution playground, intended for **Ludex Village** caretakers—especially **Naru's Cody 3**—to read and adapt.

## Contents

- Dated experiment folders: `experiments/YYYY-MM-DD/<name>/`
- Typical folder: README, stdlib-only Python, tests runnable with `python3 -B -m unittest` inside the folder.

## Layout

See the Korean section above; structure is the same.

## Experiment index (139 entries)

| Date | Folder | Summary |
|------|--------|---------|
| 2026-10-29 | [`01-coevolution-decision-log`](experiments/2026-10-29/01-coevolution-decision-log.md) | AI–human coevolution / future society |
| 2026-10-29 | [`02-crossborder-deeptech-signal-sheet`](experiments/2026-10-29/02-crossborder-deeptech-signal-sheet.md) | Deep-tech / cross-border invest signals |
| 2026-10-31 | [`01-tokwatt-agent-energy-sketch`](experiments/2026-10-31/01-tokwatt-agent-energy-sketch.md) | 01-tokwatt-agent-energy-sketch.md |
| 2026-11-01 | [`01-mandate-agent-run-checklist`](experiments/2026-11-01/01-mandate-agent-run-checklist.md) | 01-mandate-agent-run-checklist.md |
| 2026-11-01 | [`02-dsh-superagent-borrow-notes`](experiments/2026-11-01/02-dsh-superagent-borrow-notes.md) | 02-dsh-superagent-borrow-notes.md |
| 2026-11-01 | [`03-dsh-essay-vs-prototype-delta`](experiments/2026-11-01/03-dsh-essay-vs-prototype-delta.md) | 03-dsh-essay-vs-prototype-delta.md |
| 2026-11-02 | [`01-who-takes-the-lead-handoff-checklist`](experiments/2026-11-02/01-who-takes-the-lead-handoff-checklist.md) | Shared-control handoff / Ork Track 3 — Who Takes the Lead? |
| 2026-11-02 | [`02-sbus-version-check-board-rule`](experiments/2026-11-02/02-sbus-version-check-board-rule.md) | Board pointer + handback version-check / stale-write reject — S-Bus idea only (2605.17076) |
| 2026-11-02 | [`03-board-open-pr-column`](experiments/2026-11-02/03-board-open-pr-column.md) | Board open-PR column — visibility for stuck Origin PRs (Evening Close / Watchdog) |
| 2026-11-02 | [`04-sbus-observe-checklist`](experiments/2026-11-02/04-sbus-observe-checklist.md) | S-Bus observe 1–2 cycle log fields & Checker steps (pre–hard stale_write_reject); §7 content_tip vs forge_head soft caveat |
| 2026-11-03 | [`01-copilot-trajectories-intervention-checklist`](experiments/2026-11-03/01-copilot-trajectories-intervention-checklist.md) | CloudAgent / Origin PR intervention policy — Large-Scale Study of GitHub Copilot Trajectories |
| 2026-11-03 | [`02-agentbaton-park-await-cody-fields`](experiments/2026-11-03/02-agentbaton-park-await-cody-fields.md) | Park PR #10 — await_cody_fields, fail≥2 (AgentBaton handoff on main) |
| 2026-11-04 | [`01-agentbaton-failure-escalate-handoff`](experiments/2026-11-04/01-agentbaton-failure-escalate-handoff.md) | failure-id, 연속 실패 카운트, 에스컬레이션 규칙, handoff_artifact 절차 |
| 2026-11-04 | [`02-four-bridges-deception-observation-checklist`](experiments/2026-11-04/02-four-bridges-deception-observation-checklist.md) | Village 역할 매핑, 관측 로그 컬럼, Aware/Lethal 설계 메모 (시뮬 미구현) |
| 2026-11-04 | [`03-cmu-hai-failure-taxonomy-observation-checklist`](experiments/2026-11-04/03-cmu-hai-failure-taxonomy-observation-checklist.md) | CMU HAI 12-mode taxonomy — R-primary 관측 체크리스트 (markdown only; code NONE) |
| 2026-11-04 | [`04-impassebench-escalate-to-human-ticket-schema`](experiments/2026-11-04/04-impassebench-escalate-to-human-ticket-schema.md) | ImpasseBench escalate_to_human 티켓 필드 → Team OS park/handoff (markdown only; code NONE) |
| 2026-11-04 | [`05-parallact-shared-repo-handoff-checklist`](experiments/2026-11-04/05-parallact-shared-repo-handoff-checklist.md) | ParallACT 공유 repo 다중 writer — handoff 관측 체크리스트 (markdown only; code GH Soft UNVERIFIED) |
| 2026-11-04 | [`06-care-escalate-verified-progress-checklist`](experiments/2026-11-04/06-care-escalate-verified-progress-checklist.md) | CARE dual thresholds θ_esc/θ_ret + verified-progress handoff memory → Team OS escalate/park 관측 (markdown only; code NONE) |
| 2026-11-04 | [`07-pcp-shared-human-ask-queue-checklist`](experiments/2026-11-04/07-pcp-shared-human-ask-queue-checklist.md) | PCP shared-human 질문 큐, withdrawable ask, Ork→JJ 대역폭 관측 (markdown only; code NONE) |
| 2026-11-04 | [`08-delegated-scope-affordance-violation-checklist`](experiments/2026-11-04/08-delegated-scope-affordance-violation-checklist.md) | Permitted-but-unauthorized delegation record, 3-part scope-crossing checklist, replay/A/B affordance (markdown only; code GH Soft UNVERIFIED) |
| 2026-11-04 | [`09-coworkos-delegation-evidence-contract-day-sketch`](experiments/2026-11-04/09-coworkos-delegation-evidence-contract-day-sketch.md) | CoworkOS delegation evidence contract, return boundary, ask_main (wait_ms + fallback_assumption), revision conflict-not-overwrite, mock tabletop (markdown only; code GH Soft UNVERIFIED) |
| 2026-11-04 | [`10-a2-failures-boundary-taxonomy-day-sketch`](experiments/2026-11-04/10-a2-failures-boundary-taxonomy-day-sketch.md) | A²-Failures 20-mode boundary taxonomy — Ludex/Ork handoff map, 10-handoff tag plan, Checker source rule, per-principal scoring (markdown only; code NONE; HF gated note) |
| 2026-11-04 | [`11-agentic-path-maps-brief-ux-day-sketch`](experiments/2026-11-04/11-agentic-path-maps-brief-ux-day-sketch.md) | Agentic Path Maps post-run Ork brief Alternatives not taken footer (2–3 forks), ~3-path sample norm vs 9, pre-run ask reduction (markdown only; code GH Soft UNVERIFIED; HCI n=48 Soft) |
| 2026-11-04 | [`12-pcm-proof-carrying-handoff-day-sketch`](experiments/2026-11-04/12-pcm-proof-carrying-handoff-day-sketch.md) | PCM proof-carrying Smith→Checker handback — tests_passed evidence shape, proven/unproven/failed, inject F1–F3 (markdown only; PCM-protocol Soft UNVERIFIED) |
| 2026-11-04 | [`13-concordat-typed-session-protocol-day-sketch`](experiments/2026-11-04/13-concordat-typed-session-protocol-day-sketch.md) | Concordat typed-session Ork protocol draft→checked→@human→shipped, tool_calls=N R→Smith budget, subclass reject-at-definition, pressure checklist (markdown only; code Soft UNVERIFIED / pre-alpha) |
| 2026-11-04 | [`14-reviewer-gate-recovery-day-sketch`](experiments/2026-11-04/14-reviewer-gate-recovery-day-sketch.md) | Beyond Division of Labor — Reviewer gate vs forced external submit, recovery-after-first-fail checklist, Ork fail≥2 vs outside verdict (markdown only; AAMAS2027-AgentProtocols Soft UNVERIFIED; HF optional) |
| 2026-11-04 | [`15-inbox-coordination-primitive-design-note`](experiments/2026-11-04/15-inbox-coordination-primitive-design-note.md) | Inbox push vs pull for Ork ask-queue; four inbox decisions; push ~97% stale re-proposal (Soft; markdown only; code NONE) |
| 2026-11-04 | [`16-inter-agent-influence-checker-gate-checklist`](experiments/2026-11-04/16-inter-agent-influence-checker-gate-checklist.md) | Inter-Agent Influence baseline/persuasion/deception/coercion → Ork→Checker approve gate, evidence-only mitigation, flip_rate.csv plan (markdown only; code GH Soft UNVERIFIED; HF gated Soft) |
| 2026-11-04 | [`17-dependabot-apm-skill-pin-checklist`](experiments/2026-11-04/17-dependabot-apm-skill-pin-checklist.md) | Dependabot APM apm.yml skill-pack pin shapes, package-ecosystem: apm, SHA→tag behavior, Ludex/playground skill drift 관측 (markdown only; Soft UNVERIFIED; no live Dependabot) |
| 2026-11-04 | [`18-bridge-handoff-frontier-soft-sketch`](experiments/2026-11-04/18-bridge-handoff-frontier-soft-sketch.md) | BRIDGE handoff frontier — contract.yaml facts/roles, gap primitives ASK/INTEGRATE/VERIFY/DECOMPOSE/RETRIEVE, selective gate ≠ always intervene (markdown only; code Soft UNVERIFIED, no public GH) |
| 2026-11-04 | [`19-atc-role-contract-soft-sketch`](experiments/2026-11-04/19-atc-role-contract-soft-sketch.md) | ATC role contract Soft sketch — Ork/R/Smith/Checker roles.yaml, drift 관측 rubric (markdown only; code GH Soft UNVERIFIED; Soft no runtime) |
| 2026-11-04 | [`20-soei-evidence-intent-ledger-design-note`](experiments/2026-11-04/20-soei-evidence-intent-ledger-design-note.md) | Soei hash-chained ledger sketch, completion claim ≠ proof, corpus stats cite only (markdown only; code NONE; Soft no runtime) |
| 2026-11-04 | [`21-remedyfabric-quorum-receipt-day-sketch`](experiments/2026-11-04/21-remedyfabric-quorum-receipt-day-sketch.md) | RemedyFabric Worker→Smith / Verifier+Challenger→Checker / Governor→policy / Release→Ork, quorum receipt JSON sketch, forged PASS + duplicate identity refuse; KEEP Top weak (Apache-2.0, ★0, idle since 2026-08-14, GOAI;... |
| 2026-11-04 | [`22-coordination-tax-harness-dry-run-sketch`](experiments/2026-11-04/22-coordination-tax-harness-dry-run-sketch.md) | Coordination Tax harness dry-run checklist (KEEP repo); α / f / r Ork plugs; dry-run ≠ ~$80 paid live (markdown only; harness not vendored) |
| 2026-11-04 | [`23-replication-corroboration-evidential-dependence-design-note`](experiments/2026-11-04/23-replication-corroboration-evidential-dependence-design-note.md) | Replication vs corroboration — RRI / lineage quotient Soft sketch; Checker R-pick vs X-pick double-count guard (markdown only; code NONE; Soft UNVERIFIED) |
| 2026-11-04 | [`24-mascal-prompt-confidence-recheck-design-note`](experiments/2026-11-04/24-mascal-prompt-confidence-recheck-design-note.md) | MASCAL-shaped prompt handoff confidence + Checker/Ork trust vs recheck (markdown only; code NONE; no RL; Soft UNVERIFIED) |
| 2026-11-04 | [`25-waybill-ork-smith-checker-day-sketch`](experiments/2026-11-04/25-waybill-ork-smith-checker-day-sketch.md) | Waybill Ork→Smith→Checker; KEEP-with-caveats (weak Top) — NO LICENSE (method-borrow OK / code-reuse NOT); ★0 ~4mo idle; Handover Apache-2.0 compare; Act1–4 R prior session; Checker turn: /health only; pytest 69 R-only |
| 2026-11-04 | [`26-handover-ork-smith-checker-day-sketch`](experiments/2026-11-04/26-handover-ork-smith-checker-day-sketch.md) | Handover Ork scaffold / Smith fill / Checker lint+verify_cmd; YAML header sketch; Top Apache-2.0 (prefer vs Waybill NO LICENSE); scaffold --repo drift OK + placeholder header INVALID; bench trap coverage deterministic... |
| 2026-11-04 | [`27-pc2-lean-proof-handoff-checklist`](experiments/2026-11-04/27-pc2-lean-proof-handoff-checklist.md) | PC2 proof receipt + Lean mechanization map → Ork→Smith→Checker handoff; GPL no vendoring; Airlock + lake build Soft (markdown only; code NONE) |
| 2026-11-04 | [`28-revocation-executable-outcome-contract-design-note`](experiments/2026-11-04/28-revocation-executable-outcome-contract-design-note.md) | Revocation C0–C5 bounded outcome contract → capability revoke / evidence withdraw / handoff invalidate (Ork→Smith→Checker); JSON checklist sketch (markdown only; code NONE; Soft UNVERIFIED) |
| 2026-11-04 | [`29-evidence-guided-recovery-design-note`](experiments/2026-11-04/29-evidence-guided-recovery-design-note.md) | Evidence-Guided ambiguous tool outcomes → evidence-bound plans, guided checks, refuse without evidence (Ork→Smith→Checker); JSON checklist sketch (markdown only; code NONE; Soft UNVERIFIED) |
| 2026-11-04 | [`30-drs-3-hop-forge-break-day-sketch`](experiments/2026-11-04/30-drs-3-hop-forge-break-day-sketch.md) | DRS Ork→Smith→tool 3-hop receipt sketch; middle prev_dr_hash tamper → CHAIN_BREAK forge-evidence note (OkeyAmy/DRS Top Apache-2.0; markdown only; partial go test only — no full docker E2E) |
| 2026-11-04 | [`31-delegateos-dct-orchestrator-receipt-revoke-sketch`](experiments/2026-11-04/31-delegateos-dct-orchestrator-receipt-revoke-sketch.md) | DelegateOS DCT 위임·감쇠·attestation receipt·revoke/verify → Ork→Smith→Checker (markdown only; NO LICENSE → method-borrow OK / code-reuse NOT) |
| 2026-11-04 | [`32-agent-role-contracts-preflight-checklist`](experiments/2026-11-04/32-agent-role-contracts-preflight-checklist.md) | Agent Role Contracts bundle/task/handoff 선언 preflight → Ork→Smith→Checker (markdown only; MIT Top KEEP #3; CLI not run this turn) |
| 2026-11-04 | [`33-orchestra-theme-role-contract-overlap-design-note`](experiments/2026-11-04/33-orchestra-theme-role-contract-overlap-design-note.md) | Orchestra Soft KEEP (theme overlap) — agent-orchestra Soft pointer (ideas only, not run, not Top); Ork→Smith→Checker; PASS≠authority (markdown only; code NONE) |
| 2026-11-04 | [`34-c-base-contract-quotient-delegation-design-note`](experiments/2026-11-04/34-c-base-contract-quotient-delegation-design-note.md) | C-BASE Soft KEEP (caveats) — quotient work order vs mission-only; Ork→Smith→Checker + JSON sketch (markdown only; kernel/campaign on publication / not released — Soft UNVERIFIED) |
| 2026-11-04 | [`35-specgate-governed-handoff-spec-gate-refuse-design-note`](experiments/2026-11-04/35-specgate-governed-handoff-spec-gate-refuse-design-note.md) | SpecGate Soft KEEP — approved Context Pack handoff, readiness/delivery spec gate refuse; Ork→Smith→Checker (markdown only; pin thanhtung2693/specgate; runtime Soft UNVERIFIED) |
| 2026-11-04 | [`36-watchdog-loopbreaker-gate-design-note`](experiments/2026-11-04/36-watchdog-loopbreaker-gate-design-note.md) | Watchdog Soft KEEP-with-caveats — Top pins loopbreaker + loop-gate; in-loop stall + offline STASIS/EXACT_REPEAT; progress score from caller; loopbreaker pytest Soft UNVERIFIED this VM; Ork→Smith→Checker (markdown only... |
| 2026-11-04 | [`37-wrapup-picode-handback-statuses-design-note`](experiments/2026-11-04/37-wrapup-picode-handback-statuses-design-note.md) | picode-wrapup — upstream done/caveat/needs_you handback contract for Ork→Smith→Checker (Top; markdown only; code NONE) |
| 2026-11-04 | [`38-agent-mailbox-invariants-design-note`](experiments/2026-11-04/38-agent-mailbox-invariants-design-note.md) | agent-mailbox claim-once / read receipts / thread-cap→waiting-human / REQUIERE_HUMANO — Ork→Smith→Checker 불변식 스케치 (markdown only) |
| 2026-11-04 | [`39-hush-soft-design-note`](experiments/2026-11-04/39-hush-soft-design-note.md) | Hush SILENT/SPEAK/ASK restraint + addressing tiers → Ork→Smith→Checker Soft quiet-channel analog (markdown only; MIT Soft UNVERIFIED) |
| 2026-11-04 | [`40-agent-handoff-ledger-soft-design-note`](experiments/2026-11-04/40-agent-handoff-ledger-soft-design-note.md) | agent-handoff-ledger Soft KEEP — shared state, one-writer lease, bounded handoffs → Ork→Smith→Checker 패턴 메모 (markdown only; GH Soft UNVERIFIED; upstream no tests) |
| 2026-11-04 | [`41-theory-of-scene-soft-design-note`](experiments/2026-11-04/41-theory-of-scene-soft-design-note.md) | Theory of Scene Soft KEEP — shared scene + public role vs ToM symmetry trap; Ork→Smith→Checker situational analogy (markdown only; no-code 2609.32939; Soft→Top forbidden) |
| 2026-11-04 | [`42-axl-protocol-handoff-design-note`](experiments/2026-11-04/42-axl-protocol-handoff-design-note.md) | AXL Soft KEEP-with-caveats — verbs + store:<sha> + validator → Ork→Smith→Checker handoff (MIT axl-protocol; Checker 262 passed (unittest in tools/); no SQLite/DSH/Feishu port (hard rule); ledger ≤21 / anti-laundering ... |
| 2026-11-04 | [`43-stallwatch-progress-gate-design-note`](experiments/2026-11-04/43-stallwatch-progress-gate-design-note.md) | stallwatch post-run stall/progress trace gate — Top KEEP-with-caveats (MIT + Checker 66 passed); progress_score in upstream stallwatch/report.py; Soft callout only for R-local glue_progress.py (markdown only; no vendo... |
| 2026-11-04 | [`44-boba-when-to-speak-gate-design-note`](experiments/2026-11-04/44-boba-when-to-speak-gate-design-note.md) | Boba when-to-speak Top — θ/debounce/feedback borrow only; MIT + Checker 51 (Top); VM Soft UNVERIFIED; beside Hush Soft #50 (markdown only; code NONE) |
| 2026-11-04 | [`45-hier-memo-agents-soft-design-note`](experiments/2026-11-04/45-hier-memo-agents-soft-design-note.md) | hier-memo-agents DAG planner–executor, shared blackboard, topic reuse, citation verify() → Ork→Smith→Checker provenance analogy (markdown only; Soft KEEP Apache-2.0; GH Soft UNVERIFIED) |
| 2026-11-04 | [`46-maestro-supervisor-soft-design-note`](experiments/2026-11-04/46-maestro-supervisor-soft-design-note.md) | maestro-supervisor Soft KEEP — Maestro fleet stuck radar, fake-done verdict, handover/rescue skim; vitest Soft UNVERIFIED; Ork→Smith→Checker; light analogy to 36-watchdog (PR #47) + 43-stallwatch (PR #54) (markdown on... |
| 2026-11-04 | [`47-handraiser-capa-soft-design-note`](experiments/2026-11-04/47-handraiser-capa-soft-design-note.md) | wave10 Soft HANDRAISER + CAPA — listener interrupt & floor-taking (arXiv 2604.06452 + 2609.03923; Soft KEEP; Soft→Top forbidden) |
| 2026-11-04 | [`48-append-only-claim-board`](experiments/2026-11-04/48-append-only-claim-board/) | Top KEEP — victorkwak/baton append-only claim board; sketch 48-append-only-claim-board/ (cargo test 4/4 @ rustc 1.83) |
| 2026-11-04 | [`49-handback-directive`](experiments/2026-11-04/49-handback-directive/) | Top KEEP-with-caveats — agent-bridge-mcp directive-only @ 7ffe3577…; sketch 49-handback-directive/ (python -m pytest) |
| 2026-11-04 | [`50-claim-vs-verified-ledger`](experiments/2026-11-04/50-claim-vs-verified-ledger/) | 50-claim-vs-verified-ledger |
| 2026-11-04 | [`50-claim-vs-verified-ledger-design-note`](experiments/2026-11-04/50-claim-vs-verified-ledger-design-note.md) | surlymochan/swrm pin 7a565c05… — Team OS self-claim vs host-verified vs accepted lanes + adjust_status_for_verify (Top KEEP-with-caveats; Python sketch + unittest) |
| 2026-11-04 | [`51-fael-memory-pointers-soft-design-note`](experiments/2026-11-04/51-fael-memory-pointers-soft-design-note.md) | fael Soft KEEP — memory pointers scoped to opened/edited file (Ork→Smith→Checker analogy; pin 7e9044220fcca5c371cb743fd9df4fabae99e20d; markdown only; Soft UNVERIFIED) |
| 2026-11-04 | [`52-ontrack-unreliable-progress-bar-soft-design-note`](experiments/2026-11-04/52-ontrack-unreliable-progress-bar-soft-design-note.md) | Soft KEEP — OnTrack + Unreliable Progress Bar (arXiv cite ID + title only; Soft→Top forbidden; code NONE) |
| 2026-11-04 | [`53-shut-up-budget-cooldown`](experiments/2026-11-04/53-shut-up-budget-cooldown/) | 53-shut-up-budget-cooldown |
| 2026-11-04 | [`53-shut-up-budget-cooldown-soft-design-note`](experiments/2026-11-04/53-shut-up-budget-cooldown-soft-design-note.md) | Soft KEEP — Shut-Up budget_max + cooldown (NO LICENSE → playground-original sketch + unittest; Soft→Top forbidden; beside Hush #39 / Boba #44) |
| 2026-11-04 | [`54-nunchi-look-again`](experiments/2026-11-04/54-nunchi-look-again/) | 날짜: 2026-11-04 |
| 2026-11-04 | [`55-pairl-extractive-rpt`](experiments/2026-11-04/55-pairl-extractive-rpt/) | 날짜: 2026-11-04 |
| 2026-11-04 | [`56-dala-round-arbiter`](experiments/2026-11-04/56-dala-round-arbiter/) | 날짜: 2026-11-04 |
| 2026-11-04 | [`57-ask-on-demand`](experiments/2026-11-04/57-ask-on-demand/) | 날짜: 2026-11-04 |
| 2026-11-04 | [`58-icg-mas`](experiments/2026-11-04/58-icg-mas/) | 날짜: 2026-11-04 |
| 2026-11-04 | [`59-a2acompress`](experiments/2026-11-04/59-a2acompress/) | 날짜: 2026-11-04 |
| 2026-11-04 | [`60-handoff-debt-notes`](experiments/2026-11-04/60-handoff-debt-notes/) | 날짜: 2026-11-04 |
| 2026-11-04 | [`61-coop-ack-floor`](experiments/2026-11-04/61-coop-ack-floor/) | 날짜: 2026-11-04 |
| 2026-11-04 | [`62-brigade-claim-fence`](experiments/2026-11-04/62-brigade-claim-fence/) | 날짜: 2026-11-04 |
| 2026-11-04 | [`63-rally`](experiments/2026-11-04/63-rally/) | 날짜: 2026-11-04 |
| 2026-11-04 | [`64-attention-manifest`](experiments/2026-11-04/64-attention-manifest/) | 날짜: 2026-11-04 |
| 2026-11-04 | [`65-handoff-patterns`](experiments/2026-11-04/65-handoff-patterns/) | 날짜: 2026-11-04 |
| 2026-11-05 | [`01-coworkos-revision-checked-leases`](experiments/2026-11-05/01-coworkos-revision-checked-leases/) | CoworkOS revision-checked shared resources, lease vocabulary, Inbox/Jobs wake cites, ask_main bounded wait + fallback — Team OS handoff/claim lanes |
| 2026-11-05 | [`w14-arc-grammar`](experiments/2026-11-05/w14-arc-grammar/) | Lab Dig Wave14 Top #3 · Team OS playground · do not merge without Ork review. |
| 2026-11-05 | [`w14-phase-deadline`](experiments/2026-11-05/w14-phase-deadline/) | Clean-room phase budget + bounded extension helpers for Team OS runs. |
| 2026-11-05 | [`w14-silence-expiry`](experiments/2026-11-05/w14-silence-expiry/) | Track: Top KEEP (clean-room day-sketch) |
| 2026-11-05 | [`w14-sundial`](experiments/2026-11-05/w14-sundial/) | Sundial @ pin 74ede107 — unseen-time + wall ceiling + ≤3 pings + no-LLM watcher method; doctrine-ban vs informed non-objection → Top #1 on_expiry (PR #78) |
| 2026-11-05 | [`w14-whose-turn`](experiments/2026-11-05/w14-whose-turn/) | whose-turn @ pin 2919084 — P2 session exit, P4 monitoring heartbeat, snapshot board label (Soft KEEP; not baton #59 / Brigade #73) |
| 2026-11-05 | [`w14-yukh`](experiments/2026-11-05/w14-yukh/) | Yukh 13-type envelope lifecycle checklist, verdict-before-handoff, immutable evidence refs, RFC-0016/0021 reading pointers — no relay port |
| 2026-11-06 | [`01-flyhash-agent-memory`](experiments/2026-11-06/01-flyhash-agent-memory/) | FlyHash vs SimHash vs HNSW recall@k on playground markdown corpus (upstream flyhash-agent-memory v1.0 pin) |
| 2026-11-06 | [`w15-evidence-gate`](experiments/2026-11-06/w15-evidence-gate/) | Evidence-Gated Authority Layer B day-sketch: disposition + mechanical certificate gate (arXiv:2611.05390, upstream v2.0.0 @ f232d437…) |
| 2026-11-06 | [`w15-handoff-gate`](experiments/2026-11-06/w15-handoff-gate/) | Wave15 Soft1 Agent Handoff Gate decision table (KEEP Soft; pin zsoXi/agent-handoff-gate @ dd4d590c) |
| 2026-11-06 | [`w15-harness-scorer`](experiments/2026-11-06/w15-harness-scorer/) | The Harness Is the Model — action-log scorer invariants (pin 42e2ba3056a6404253e926dfd6be595309379c3a, synthetic traces only) |
| 2026-11-06 | [`w15-sepm`](experiments/2026-11-06/w15-sepm/) | Wave15 Soft2 SEPM store-free EvidenceTier + DAG (KEEP Soft; pin cookieApril/SEPM @ 083232a9) |
| 2026-11-06 | [`w15-tooling-memory`](experiments/2026-11-06/w15-tooling-memory/) | Wave15 Soft4 tooling-memory principles checklist (KEEP Soft; pin apache/tooling-memory @ 4662cc2d) |
| 2026-11-06 | [`w15-zsc-cfd`](experiments/2026-11-06/w15-zsc-cfd/) | Wave15 Soft3 ZSC CFDs method-cite checklist (KEEP Soft; UNVERIFIED runnable; pin ahayler/zsc-llm-agents @ 739c2497) |
| 2026-11-07 | [`01-more-agents-reliability`](experiments/2026-11-07/01-more-agents-reliability/) | More Agents, More Reliable? clean-room TMR composition (KEEP Soft; method sketch of arXiv 2611.07140; not a reproduction of Table 1(a) or the 270-call study) |
| 2026-11-07 | [`w16-atc`](experiments/2026-11-07/w16-atc/) | ATC role-contract admission with post-revision re-check (KEEP Soft; method-cite of arXiv 2611.04321; upstream is a coming-soon stub; not a reproduction of energy, leakage, encoder, or constrained-regeneration results) |
| 2026-11-07 | [`w16-blast-radius`](experiments/2026-11-07/w16-blast-radius/) | Airlock default containment tier (KEEP Top; method-borrow of arXiv 2611.06727; not a reproduction of the 1,832-run study) |
| 2026-11-07 | [`w16-fail-signatures`](experiments/2026-11-07/w16-fail-signatures/) | Closed sequential failure signatures and stop-and-report early-stop (KEEP Top; method-cite of arXiv 2611.04142; not a reproduction of paper F1, coverage, or token-savings figures) |
| 2026-11-07 | [`w16-overseer-flip`](experiments/2026-11-07/w16-overseer-flip/) | Inter-Agent Influence overseer flip scorer (KEEP Top; method-borrow of arXiv 2611.04556; measurement only, not a binding gate; not a reproduction of paper percentage-point results) |
| 2026-11-08 | [`01-routebr`](experiments/2026-11-08/01-routebr/) | Route Before Response fail-closed routing (method sketch of arXiv 2611.07534; not a reproduction of the paper's confirmatory-split result) |
| 2026-11-08 | [`w17-disclosure-policy`](experiments/2026-11-08/w17-disclosure-policy/) | Disclosure-policy illustration (method sketch of arXiv 2611.07667; scripted counterexample, not a replication of the paper's model results) |
| 2026-11-08 | [`w17-failure-baseline`](experiments/2026-11-08/w17-failure-baseline/) | Failure-prediction baselines (method sketch of arXiv 2611.08285; evaluation critique, not a reproduction of SWE-bench AUROC) |
| 2026-11-08 | [`w17-memory-scope`](experiments/2026-11-08/w17-memory-scope/) | Memory scope write/read holds (method sketch of arXiv 2611.07554; not a proven defense) |
| 2026-11-08 | [`w17-revision-contract`](experiments/2026-11-08/w17-revision-contract/) | Call-level revision contracts (method sketch of arXiv 2611.06967; not a reproduction of the paper's media-workflow results) |
| 2026-11-08 | [`w17-source-authority`](experiments/2026-11-08/w17-source-authority/) | Decision-field source authority (method sketch of arXiv 2611.07640; paper method only; no repo code or data copied) |
| 2026-11-09 | [`01-step-ledger`](experiments/2026-11-09/01-step-ledger/) | A tiny, deterministic, offline toy in which an environment and a trainer talk |
| 2026-11-09 | [`w18-covert-sidegoal`](experiments/2026-11-09/w18-covert-sidegoal/) | A toy shape test for two trace monitors |
| 2026-11-09 | [`w18-decaf-dimensions`](experiments/2026-11-09/w18-decaf-dimensions/) | A proposal-format validator: a proposed change to an agent configuration |
| 2026-11-09 | [`w18-effect-reversibility`](experiments/2026-11-09/w18-effect-reversibility/) | A small, deterministic method sketch of one idea from the research agenda in |
| 2026-11-09 | [`w18-odd-llm-checklist`](experiments/2026-11-09/w18-odd-llm-checklist/) | A documentation-hygiene checklist for LLM-driven agent-based models, organised |
| 2026-11-09 | [`w18-phantom-consensus`](experiments/2026-11-09/w18-phantom-consensus/) | A small, deterministic method sketch of one idea from |
| 2026-11-09 | [`w18-skill-assurance`](experiments/2026-11-09/w18-skill-assurance/) | A small, deterministic method sketch of one idea from |
| 2026-11-10 | [`w19-authz-drift`](experiments/2026-11-10/w19-authz-drift/) | An agent that stays on the user's goal but reaches past its own grant, and a |
| 2026-11-10 | [`w19-engram-release`](experiments/2026-11-10/w19-engram-release/) | A skill's experience records stay in retrieval until a check shows the |
| 2026-11-10 | [`w19-guardrail-order`](experiments/2026-11-10/w19-guardrail-order/) | A silent guardrail-order break in a toy agent harness, and an order check |
| 2026-11-10 | [`w19-workspace-grant`](experiments/2026-11-10/w19-workspace-grant/) | One grant per workspace, issued before the action, instead of a prompt per |
| 2026-11-11 | [`w20-acf-adherence`](experiments/2026-11-11/w20-acf-adherence/) | Does an agent do what its context file says |
| 2026-11-11 | [`w20-checkable-rulebook`](experiments/2026-11-11/w20-checkable-rulebook/) | can settle that a forbidden event happened, but it cannot settle that one |
| 2026-11-11 | [`w20-evidence-linked-memory`](experiments/2026-11-11/w20-evidence-linked-memory/) | A lesson is only as good as the run it came from |
| 2026-11-11 | [`w20-fidelity-audit`](experiments/2026-11-11/w20-fidelity-audit/) | A tool pass vouches for the one artefact it ran on and says nothing about |
| 2026-11-11 | [`w20-plan-change-notice`](experiments/2026-11-11/w20-plan-change-notice/) | Acknowledging a change of objective is not the same as acting on it |
| 2026-11-12 | [`mb-fail-closed-deputy`](experiments/2026-11-12/mb-fail-closed-deputy/) | Missing evidence is not explicit denial, and silence is not consent |
| 2026-11-12 | [`w21-advice-cooldown`](experiments/2026-11-12/w21-advice-cooldown/) | only when a micro-contract for the tool applies and the suggested call |
| 2026-11-12 | [`w21-info-friction`](experiments/2026-11-12/w21-info-friction/) | Busy is not progress: when recurrent evidence brings no new resolution, |
| 2026-11-12 | [`w21-memory-admission`](experiments/2026-11-12/w21-memory-admission/) | Local success is not admission |
| 2026-11-12 | [`w21-plan-changing-ask`](experiments/2026-11-12/w21-plan-changing-ask/) | Ask for the fact that changes the plan, not just any clarification |
| 2026-11-12 | [`w21-screen-recall-sample`](experiments/2026-11-12/w21-screen-recall-sample/) | Agreement is not recall |
| 2026-11-12 | [`w21-unused-contradiction`](experiments/2026-11-12/w21-unused-contradiction/) | A flag is not a repair |
| 2026-11-13 | [`mb-creg-belief-scoring`](experiments/2026-11-13/mb-creg-belief-scoring/) | Score the whole belief trajectory, not only the endpoint |
| 2026-11-13 | [`w22-revision-selectivity`](experiments/2026-11-13/w22-revision-selectivity/) | Prestige is not selectivity: a disagreement-driven revision is judged by |
| 2026-11-13 | [`w22-spec-satisficing`](experiments/2026-11-13/w22-spec-satisficing/) | Acceptable is not compliant: a choice that drops a requirement may not be |
| 2026-11-13 | [`w22-write-precommit`](experiments/2026-11-13/w22-write-precommit/) | Commit writes before any tool result; admit a write only when every |
| 2026-11-14 | [`mb-boundary-vs-judge`](experiments/2026-11-14/mb-boundary-vs-judge/) | Choose the evaluator before the conclusion: the same episodes, scored by a |
| 2026-11-14 | [`w23-scrutiny-not-authority`](experiments/2026-11-14/w23-scrutiny-not-authority/) | Self-assessment is advisory, not a deletion authority: when an agent rates |
| 2026-11-14 | [`w23-termination-lag`](experiments/2026-11-14/w23-termination-lag/) | Once a first patch passes, later steps must not undo it |
| 2026-11-14 | [`w23-world-consistent-history`](experiments/2026-11-14/w23-world-consistent-history/) | Do not clean an agent's history into a false "done" while the world still |
| 2026-11-15 | [`mb-conversation-loss-oracle`](experiments/2026-11-15/mb-conversation-loss-oracle/) | Schema-valid is not conversation-preserving: a translated chat request can |
| 2026-11-15 | [`w24-alert-silence-is-not-fix`](experiments/2026-11-15/w24-alert-silence-is-not-fix/) | A disappearing alert is not a fix |
| 2026-11-15 | [`w24-threshold-compliance`](experiments/2026-11-15/w24-threshold-compliance/) | A high abstention rate is not threshold compliance |
| 2026-11-15 | [`w24-trust-needs-feedback`](experiments/2026-11-15/w24-trust-needs-feedback/) | Trust in an advisor needs timely external feedback |

## Mirror notice

Mirrored from private Cursor Origin repo `coevolution-lab/playground`. **Pull requests on this public mirror are not monitored.** See [`MIRROR.md`](MIRROR.md) for source SHA and checksums.
