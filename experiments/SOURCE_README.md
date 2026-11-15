# Ork Team Playground

**목적**: Ork 팀의 일일 실험 공간 — AI–인간 공진화, 미래 사회, 투자 신호, 게임 & 콘텐츠 실험

이 저장소는 Ork 팀이 일상적인 실험과 탐구를 수행하는 작업 공간입니다.

> **참고**: Ludex는 별도의 프로젝트/빌리지이며 이 저장소의 범위에 포함되지 않습니다.

## 새로운 실험 추가하기

1. `experiments/YYYY-MM-DD/` 형식으로 새 폴더 생성
2. `experiments/2026-10-29/TEMPLATE.md`를 새 날짜 폴더로 복사
3. 템플릿의 섹션을 채워 실험 진행

## 링크

- **Browse**: [https://cursor.com/codebase/coevolution-lab/playground](https://cursor.com/codebase/coevolution-lab/playground)
- **Clone**: `git clone https://origin.cursor.com/coevolution-lab/playground.git`

## 구조

```
experiments/
  YYYY-MM-DD/
    TEMPLATE.md    # 실험 템플릿
    ...            # 실험 관련 파일들
```

## 실험 인덱스 (sibling rows — folder `#`, not Origin PR `#`)

| # | 날짜 | 문서 | Tier / 비고 |
|---|------|------|-------------|
| 1 | 2026-11-05 | [01-coworkos-revision-checked-leases/DESIGN-NOTE.md](./experiments/2026-11-05/01-coworkos-revision-checked-leases/DESIGN-NOTE.md) | **Soft KEEP** / **Soft UNVERIFIED** — [CoworkOS](https://github.com/RUC-NLPIR/CoworkOS) @ tag `v0.1.3` `13e2368f…`; [2611.03178](https://arxiv.org/abs/2611.03178); method-only — [`01-coworkos-revision-checked-leases/`](./experiments/2026-11-05/01-coworkos-revision-checked-leases/) |
| 48 | 2026-11-04 | [48-append-only-claim-board-design-note.md](./experiments/2026-11-04/48-append-only-claim-board-design-note.md) | **Top KEEP** — [victorkwak/baton](https://github.com/victorkwak/baton) @ `965c8dcd…`; Rust sketch [`48-append-only-claim-board/`](./experiments/2026-11-04/48-append-only-claim-board/) |
| 49 | 2026-11-04 | [49-handback-directive-design-note.md](./experiments/2026-11-04/49-handback-directive-design-note.md) | **Top KEEP-with-caveats** — agent-bridge-mcp `evaluateOrchestratorDirective` @ `7ffe3577…`; Python sketch [`49-handback-directive/`](./experiments/2026-11-04/49-handback-directive/) |
