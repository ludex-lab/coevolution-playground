import unittest

from brigade_claim_fence_pure import Claim, RetiredHolder, refuse_stale_fence


class BrigadeClaimFencePureTests(unittest.TestCase):
    NOW = 1_700_000_000.0
    RETIRED = frozenset(
        {
            RetiredHolder(
                target="repo:org/app",
                node="node-a",
                holder="old-lease",
                generation=2,
                retired_at=NOW - 3600,
            )
        }
    )

    def test_stale_generation(self) -> None:
        r = refuse_stale_fence(
            action="renew",
            expected_generation=1,
            fence_generation=3,
            target="repo:org/app",
            node="node-a",
            holder="lease-1",
            retired=frozenset(),
            now=self.NOW,
        )
        self.assertFalse(r.ok)
        self.assertEqual(r.reason, "stale-generation")

    def test_stale_holder_without_generation(self) -> None:
        r = refuse_stale_fence(
            action="acquire",
            expected_generation=None,
            fence_generation=3,
            target="repo:org/app",
            node="node-a",
            holder="old-lease",
            retired=self.RETIRED,
            now=self.NOW,
        )
        self.assertFalse(r.ok)
        self.assertEqual(r.reason, "stale-holder")

    def test_acquire_retry_allows_pre_acquire_generation(self) -> None:
        live = Claim(target="repo:org/app", holder="lease-1", generation=2)
        r = refuse_stale_fence(
            action="acquire",
            expected_generation=2,
            fence_generation=3,
            target="repo:org/app",
            node="node-a",
            holder="lease-1",
            retired=frozenset(),
            now=self.NOW,
            live=live,
            live_node="node-a",
        )
        self.assertTrue(r.ok, r.reason)

    def test_retired_horizon_expired_allows_acquire(self) -> None:
        expired = frozenset(
            {
                RetiredHolder(
                    target="repo:org/app",
                    node="node-a",
                    holder="old-lease",
                    generation=2,
                    retired_at=self.NOW - 8 * 86400,
                )
            }
        )
        r = refuse_stale_fence(
            action="acquire",
            expected_generation=None,
            fence_generation=3,
            target="repo:org/app",
            node="node-a",
            holder="old-lease",
            retired=expired,
            now=self.NOW,
        )
        self.assertTrue(r.ok)


if __name__ == "__main__":
    unittest.main()
