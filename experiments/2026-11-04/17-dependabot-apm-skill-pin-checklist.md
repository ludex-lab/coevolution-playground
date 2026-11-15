# Dependabot × APM — shared skill-pack pin & drift (design checklist)

**날짜**: 2026-11-04  
**Primary**: [GitHub Changelog — Dependabot version updates for APM (2026-11-03)](https://github.blog/changelog/2026-11-03-dependabot-version-updates-support-agent-package-manager/) · [microsoft/apm README](https://github.com/microsoft/apm) · [Dependabot supported ecosystems — APM](https://docs.github.com/en/code-security/reference/supply-chain-security/supported-ecosystems-and-repositories#apm)

**Code**: **Soft UNVERIFIED** — no `apm.yml`, `apm.lock.yaml`, or `.github/dependabot.yml` `apm` entry wired in playground today; **no live Dependabot version-update fire** on this repo for this sprint.

## Changelog pointer (version updates only)

From the [2026-11-03 changelog](https://github.blog/changelog/2026-11-03-dependabot-version-updates-support-agent-package-manager/) (paraphrase for checklist use):

- Dependabot **version updates** now cover git dependencies declared in **`apm.yml`** and can regenerate **`apm.lock.yaml`** when present.
- Scope is **version updates**, **not security updates**.
- GA on github.com; GHES **3.24** (changelog).

Playground **does not** claim a verified Dependabot run, open bot PR, or lockfile diff in this sketch.

---

## Example `apm.yml` pin shapes (shared skill packs)

Following [microsoft/apm README](https://github.com/microsoft/apm) dependency string conventions (`owner/repo/path#ref`). Illustrative only — paths are placeholders for a **shared org skill pack**, not installed here.

```yaml
# apm.yml — design sketch for Ludex / playground shared skills (NOT committed)
name: playground-agent-context
version: 0.0.0-sketch
targets:
  - cursor
dependencies:
  apm:
    # SemVer tag pin — Dependabot can bump to latest non-prerelease tag (docs)
    - coevolution-lab/ludex-skills/skills/team-os-handoff#v1.2.0
    # Virtual package path + package-scoped tag (docs: prefix must match package name)
    - coevolution-lab/ludex-skills/skills/review-gate#review-v1.0.3
    # Full 40-char commit SHA — Dependabot moves only to commit of latest annotated, non-prerelease release tag; adds `# vX.Y.Z` comment (docs)
    - coevolution-lab/ludex-skills#aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
    # Whole bundle tag (README sample style)
    - microsoft/apm-sample-package#v1.0.0
  devDependencies:
    apm:
      - coevolution-lab/playground-skills/skills/experiment-index-norm#v0.4.1
```

**Pin hygiene (docs + README, Soft):**

| Pin | Example | Dependabot behavior (cite docs, not live-tested) |
|-----|---------|-----------------------------------------------------|
| SemVer tag | `org/pkg#v1.4.0` | Bump toward latest SemVer tag; package-scoped tags supported |
| Commit SHA (40 char) | `org/pkg#<full SHA>` | Move to commit of latest **annotated, non-prerelease** release tag; tag name as YAML comment |
| Branch | `org/pkg#main` | Latest branch commit; manifest keeps branch name; **`apm.lock.yaml` required** for updates |
| Abbreviated SHA | `org/pkg#abc1234` | **Not updated** (docs) |

**Not updated by Dependabot (docs list):** object-form entries (`git:` / `registry:` maps), `mcp:` entries, ref-less entries, local `./` paths, block-scalar / escaped quoted strings, Azure DevOps hosts, `http://` / `git://` URLs, shorthand when `registries.default` is set (unless explicit clone URL).

---

## Example `.github/dependabot.yml` snippet (`package-ecosystem: apm`)

Directory must contain **`apm.yml`** (changelog + [configuration options](https://docs.github.com/en/code-security/dependabot/dependabot-version-updates/configuration-options-for-the-dependabot.yml-file#package-ecosystem)).

```yaml
# .github/dependabot.yml — design snippet only (NOT committed)
version: 2
updates:
  - package-ecosystem: "apm"
    directory: "/"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 5
    # Optional: ignore prerelease tags (APM recognizes alpha/beta/rc — docs options reference)
    # ignore:
    #   - dependency-name: "coevolution-lab/ludex-skills/skills/review-gate"
    #     update-types: ["version-update:semver-minor"]
```

**Soft UNVERIFIED:** playground has no bot PR proving `apm lock` regeneration on merge.

---

## Ludex / playground **skill drift** (design memo)

Problem statement for Team OS (markdown only):

1. **Manual skill copies** across Ludex Village repos and `playground` experiment norms diverge without a manifest — no lockfile, no Dependabot signal.
2. **Transitive skill trees** (APM README: packages depend on packages; `apm.lock.yaml` pins hashes) are not observable in playground today; [05](./05-parallact-shared-repo-handoff-checklist.md) **joint_fail** risk applies when agents read **different skill SHAs** on the same sprint.
3. **Policy plane vs harness plane** (APM README: `apm-policy.yml` vs agent runtime) — Ork may allow a skill path while org policy would block; Dependabot PRs do not replace policy review.

### Observation checklist (skill pin / bot PR — log only)

Log when a Dependabot (or manual) APM bump touches shared skills relevant to Ludex / playground. **No automation** in this repo.

| Column | Type | Definition |
|--------|------|------------|
| `label` | tag | `observation` or **`example`** |
| `run_id` | string | Cloud Agent run or village session id |
| `manifest_path` | string | Repo-relative `apm.yml` path |
| `dependency_key` | string | APM string entry (redact tokens) |
| `pin_before` | string | Tag, full SHA, or branch ref before change |
| `pin_after` | string | After Dependabot or human bump |
| `lockfile_regen` | bool | `apm.lock.yaml` diff present (if lockfile exists) |
| `bot_pr_url` | string \| null | Dependabot PR URL — **null** until live fire |
| `drift_class` | enum | `semver_tag` \| `sha_to_tag_comment` \| `branch_tip` \| `manual_hand_edit` \| `policy_block` \| `none_observed` |
| `team_os_impact` | enum | `norm_mismatch` \| `handoff_skill_delta` \| `checker_gate_text_delta` \| `none_observed` |
| `notes` | string | Pointers: SHAs, PR ids; link [01](./01-agentbaton-failure-escalate-handoff.md) `log_path` if escalate followed drift |

### Example row (**example** — fictional, plausible)

| label | run_id | manifest_path | dependency_key | pin_before | pin_after | lockfile_regen | bot_pr_url | drift_class | team_os_impact | notes |
|-------|--------|---------------|----------------|------------|-----------|----------------|------------|-------------|----------------|-------|
| **example** | `ca-run-apm-sketch-7f2` | `apm.yml` | `coevolution-lab/ludex-skills/skills/team-os-handoff#v1.1.0` | `#v1.1.0` | `#v1.2.0` | true | null | `semver_tag` | `norm_mismatch` | Design-only row; **no** verified Dependabot PR on playground; JJ would reconcile experiment README norms after skill bump |

---

## Cross-links (optional)

- Shared-repo writers + skill skew → [05](./05-parallact-shared-repo-handoff-checklist.md) `joint_fail_local_pass`.
- Human park on impasse (not version bump) → [04](./04-impassebench-escalate-to-human-ticket-schema.md).
- Parallel agents reading different context → [07](./07-pcp-shared-human-ask-queue-checklist.md) queue norms.

---

## Out of scope (2026-11-04)

- DSH / Feishu / SQLite / daemon / headcount ports  
- Running `apm install`, `apm lock`, or adding real `apm.yml` to playground in this PR  
- **Live Dependabot** verification, security updates, or private-registry wiring  
- Weak social posts as primary evidence (changelog + microsoft/apm + GitHub docs only)  
- Editing bodies of [01](./01-agentbaton-failure-escalate-handoff.md)–[07](./07-pcp-shared-human-ask-queue-checklist.md) or **PR #10** Copilot trajectory / park description  

---

## Status

- [x] Planning (design checklist sketch)  
- [ ] In Progress (no `apm` manifest or Dependabot config)  
- [ ] Complete  

**Next step:** When Ludex publishes a shared `apm.yml`, add manifest + `dependabot.yml` `apm` entry on a **separate** PR; re-run this checklist against the first bot PR — still **Soft** until observed.

---

## relied_on (Soft UNVERIFIED for live fire)

| Source | Use in this doc |
|--------|-----------------|
| [GitHub Changelog 2026-11-03 — Dependabot APM version updates](https://github.blog/changelog/2026-11-03-dependabot-version-updates-support-agent-package-manager/) | GA scope: `apm.yml`, lock regen, **version updates not security** |
| [microsoft/apm README](https://github.com/microsoft/apm) | `apm.yml` / `dependencies.apm` string shapes, lockfile, sample `#v1.0.0` pins |
| [Dependabot supported ecosystems — APM section](https://docs.github.com/en/code-security/reference/supply-chain-security/supported-ecosystems-and-repositories#apm) | Pin-type table: SemVer tag, full SHA→annotated non-prerelease tag + comment, branch + lockfile |
| [Dependabot `package-ecosystem` reference](https://docs.github.com/en/code-security/dependabot/dependabot-version-updates/configuration-options-for-the-dependabot.yml-file#package-ecosystem) | YAML value `apm` |

**Not relied on:** live Dependabot run on `coevolution-lab/playground`; `@automater_ai` or other weak X posts as primary.
