# mb-fail-closed-deputy

Missing evidence is not explicit denial, and silence is not consent. This
folder is a small, deterministic method sketch inspired by
[arXiv 2611.13355 (DEPUTYBENCH)](https://arxiv.org/abs/2611.13355). It is
not a reproduction of that paper, and it is not law, policy or a team rule.
It uses only the Python standard library, makes no network calls and writes
no files.

## The three cases

A deputy receives a request with a permission record (`granted`, `denied`,
`unknown`) and an evidence grade (`complete`, `partial`, `missing`).
`deputy.classify` maps each request to one case:

| case | inputs |
|---|---|
| `permitted` | permission `granted` and evidence `complete` |
| `explicit_deny` | permission `denied`, whatever the evidence grade |
| `missing_evidence` | permission `unknown`, or `granted` without complete evidence |

## The two policies

- `fail_closed` dispatches only on `permitted`. It refuses both
  `explicit_deny` and `missing_evidence`, and the decision record holds the
  two reason codes apart, so "we were told no" never reads like "we could
  not verify yes".
- `optimistic_if_unknown` is the baseline under study. It still refuses an
  explicit deny, but it dispatches when evidence is missing, which treats
  silence as consent.

Under both policies, malformed input, unknown fields and unknown policies
refuse with reason `config_error`; they never dispatch. A request may carry
a `wait` block with `timeout_s`. A timeout without a declared `on_expiry`
is a `config_error`, and `refuse` is the only accepted `on_expiry`. An
expired wait refuses with reason `expired` on every case, including a
permitted one and an explicit deny, and records the case's own reason in
`prior_reason`. An unknown never resolves to dispatch.

## Input checks

- Every input is checked by exact type (`type(x) is str`, `dict`, `int`,
  `bool`), not by `isinstance` or equality alone. A subclass that pretends
  to equal a valid value (for example a `str` subclass whose `__eq__`
  always says yes) is a `config_error`, for the request, its field names,
  `permission`, `evidence`, `action`, `request_id`, the `wait` block and
  the `policy` argument.
- Every value in a decision record is `None` or one of the module's own
  constants. The only caller value echoed is an exact-`str` `request_id`,
  and only once the whole request has validated; every `config_error`
  record carries `request_id` `None`. On expiry the decision is the module's `refuse` constant, never the
  caller's `on_expiry` object.
- A `policy` argument that is not an exact `str` naming a known policy is
  recorded as `invalid_policy`, so a record never claims `fail_closed` (or
  any policy) under a spoofed value.
- `decide()` does not raise on bad input. Inputs whose `__eq__`,
  `__hash__` or `__str__` raise are rejected by type before they are
  compared, and any internal error is caught and refused with
  `config_error`.
- No field of a request is read before `validate()` passes. A lookup on
  an unvalidated mapping can run caller code: a non-`str` key whose hash
  equals `hash("request_id")` has its `__eq__` called during the lookup,
  and a `dict` subclass can override `get` or `__getitem__`. Such code could
  rewrite `unknown`/`missing` into `granted`/`complete` before the check.
  Validation rejects non-`str` keys and `dict` subclasses by iterating keys
  and checking types only, so that code never runs and the request refuses
  with `config_error`.

## What we measured

`measure.py` runs both policies over 54 enumerated synthetic cases
(3 permission values x 3 evidence grades x 6 actions: 6 `permitted`,
18 `explicit_deny`, 30 `missing_evidence`). It reports the unsafe dispatch
rate on missing-evidence cases and on explicit-deny cases, and the gap
between the two in percentage points:

```
policy                 permitted%  missing_ev%   expl_deny%   gap_pp
fail_closed                 100.0          0.0          0.0      0.0
optimistic_if_unknown       100.0        100.0          0.0    100.0
n_cases=54 (synthetic set only)
```

These figures describe our synthetic set and two hand-written rules. The
gap is there by construction, and it says nothing about how any model
behaves. The sketch shows that the gap can be told apart and tested when
the reason codes stay distinct.

For context only: the paper's authors report, for their own models, that
restricted execution was more frequent with missing evidence than with
explicit non-permission. The abstract hedges this result. The authors call
it a secondary analysis and report it with a confidence interval. A
post-hoc analysis in the same abstract places most masked-condition
executions in a small group of privacy tasks, and the authors say the
difference is much smaller outside those tasks; they describe this as task
structure and audited outcomes, not an identified internal mechanism.
Their figures, the interval and the concentration counts are recorded,
quoted, attributed and marked UNVERIFIED in `paper_evidence.json`. We have
not checked them and do not claim them.

## Files

- `deputy.py`: validation, classification and `decide(request, policy)`.
- `cases.py`: the enumerated case set, with expected labels taken from a
  separate table.
- `measure.py`: prints the table, then the same result as one JSON line on
  stdout.
- `test_deputy.py`: unittest suite.
- `paper_evidence.json`: the authors' figures, UNVERIFIED by us.
- `mutants.py`: 28 code mutants and 5 world (case set) mutants. Each one
  must make the suite fail. Code mutants either wrap a deputy function or
  replace one exact snippet of `deputy.py` in memory; they include the
  spoof breaches (isinstance in place of exact type, echoing the caller's
  `on_expiry` or policy, no try/except), expiry skipped on permitted or
  deny cases, a narrower baseline, the validator branches, and a
  `request_id` read before validation or on the `config_error` path.

## Run

From this folder, with system `python3`:

```
python3 -m unittest
python3 -m unittest test_deputy.py
python3 measure.py
python3 mutants.py
```

## Limits

- The cases are synthetic and balanced by enumeration, not sampled from
  real requests.
- There is no model in the loop. The baseline is a rule, not an agent.
- Evidence completeness is given as an input label. Judging whether
  evidence really is complete is out of scope here.
