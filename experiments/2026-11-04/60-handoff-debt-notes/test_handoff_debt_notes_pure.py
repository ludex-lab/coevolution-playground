import unittest

from handoff_debt_notes_pure import (
    STRUCTURED_FIELDS,
    git_status_is_dirty,
    validate_structured_handoff_record,
)


def _sample_fields(**overrides: str) -> dict[str, str]:
    base = {name: "UNKNOWN" for name in STRUCTURED_FIELDS}
    base["work_completed"] = "Read failing test output; no source edit yet."
    base.update(overrides)
    return base


class HandoffDebtNotesPureTests(unittest.TestCase):
    def test_git_status_is_dirty_tracked(self) -> None:
        self.assertFalse(git_status_is_dirty(""))
        self.assertFalse(git_status_is_dirty("  \n"))
        self.assertTrue(git_status_is_dirty(" M experiments/foo.py"))

    def test_git_status_is_dirty_untracked_only(self) -> None:
        self.assertTrue(git_status_is_dirty("?? scratch/out.txt"))
        self.assertFalse(git_status_is_dirty("# comment only\n"))

    def test_untracked_only_with_no_uncommitted_claim_fails_via_porcelain(self) -> None:
        fields = _sample_fields(
            work_completed="Review complete; no uncommitted changes in tracked files."
        )
        porcelain = "?? experiments/2026-11-04/tmp-notes.md"
        result = validate_structured_handoff_record(
            status_short=porcelain,
            fields=fields,
        )
        self.assertFalse(result.ok)
        self.assertTrue(
            any(i.startswith("dirty_git_contradiction:") for i in result.issues)
        )

    def test_false_clean_if_caller_ignores_untracked(self) -> None:
        """Passing git_dirty=False while porcelain has ?? would wrongly accept clean claims."""
        fields = _sample_fields(
            rollback_notes="Working tree clean; ready for handoff."
        )
        wrong = validate_structured_handoff_record(git_dirty=False, fields=fields)
        self.assertTrue(wrong.ok, wrong.issues)
        right = validate_structured_handoff_record(
            status_short="?? artifacts/local-only.md",
            fields=fields,
        )
        self.assertFalse(right.ok)

    def test_clean_git_honest_notes_ok(self) -> None:
        fields = _sample_fields()
        result = validate_structured_handoff_record(git_dirty=False, fields=fields)
        self.assertTrue(result.ok, result.issues)

    def test_clean_tree_no_uncommitted_changes_phrase_ok(self) -> None:
        fields = _sample_fields(
            evidence_observed="Porcelain empty; no uncommitted changes."
        )
        result = validate_structured_handoff_record(git_dirty=False, fields=fields)
        self.assertTrue(result.ok, result.issues)

    def test_dirty_git_no_change_claim_fails(self) -> None:
        fields = _sample_fields(
            work_completed="Investigated; no changes were made to source yet."
        )
        result = validate_structured_handoff_record(git_dirty=True, fields=fields)
        self.assertFalse(result.ok)
        self.assertTrue(
            any(i.startswith("dirty_git_contradiction:") for i in result.issues)
        )

    def test_dirty_git_honest_work_completed_ok(self) -> None:
        fields = _sample_fields(
            work_completed="Patched handler; `git status --short` shows modified files."
        )
        result = validate_structured_handoff_record(git_dirty=True, fields=fields)
        self.assertTrue(result.ok, result.issues)

    def test_clean_git_claims_dirty_tree_fails(self) -> None:
        fields = _sample_fields(
            evidence_observed="Repository has uncommitted changes in two files."
        )
        result = validate_structured_handoff_record(git_dirty=False, fields=fields)
        self.assertFalse(result.ok)
        self.assertIn("clean_git_contradiction:notes_claim_dirty_tree", result.issues)

    def test_missing_field_fails(self) -> None:
        fields = _sample_fields()
        del fields["rollback_notes"]
        result = validate_structured_handoff_record(git_dirty=False, fields=fields)
        self.assertFalse(result.ok)
        self.assertIn("missing_field:rollback_notes", result.issues)


if __name__ == "__main__":
    unittest.main()
