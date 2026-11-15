from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

_RULE_KEYS = frozenset(
    {"requires_approval", "ladder", "deadline_s", "deadline_seconds", "on_expiry", "quorum"}
)


class ConfigError(ValueError):
    pass


class OnExpiry(str, Enum):
    DENY = "deny"
    SAFE_FALLBACK = "safe_fallback"
    ESCALATE = "escalate"
    HOLD = "hold"


class TerminalState(str, Enum):
    APPROVED = "approved"
    FELL_BACK = "fell_back"
    DENIED_ON_TIMEOUT = "denied_on_timeout"
    HELD = "held"
    EXHAUSTED = "exhausted"


@dataclass(frozen=True, slots=True)
class Rule:
    requires_approval: bool
    ladder: tuple[str, ...]
    deadline_s: int
    on_expiry: OnExpiry
    quorum: int = 1

    def __post_init__(self) -> None:
        if self.quorum < 1:
            raise ConfigError("quorum must be at least 1")
        if self.requires_approval and not self.ladder:
            raise ConfigError("requires_approval rule needs a non-empty ladder")
        if self.requires_approval and self.deadline_s <= 0:
            raise ConfigError("deadline_s must be positive when approval is required")
        if self.quorum > len(self.ladder) and self.ladder:
            raise ConfigError("quorum can never be satisfied by this ladder")


@dataclass(frozen=True, slots=True)
class Policy:
    rules: dict[str, Rule]

    def rule_for(self, risk: str) -> Rule:
        try:
            return self.rules[risk]
        except KeyError as exc:
            raise ConfigError(f"unknown risk level {risk!r}") from exc


def _parse_on_expiry(raw: Any, path: str) -> OnExpiry:
    if raw is None:
        raise ConfigError(f"{path}: missing on_expiry when requires_approval is true")
    if isinstance(raw, str) and raw.lower() == "allow":
        raise ConfigError(f"{path}: on_expiry allow is forbidden (silence is not consent)")
    try:
        return OnExpiry(str(raw).lower())
    except ValueError as exc:
        raise ConfigError(
            f"{path}: unknown on_expiry {raw!r}, expected one of {[m.value for m in OnExpiry]}"
        ) from exc


def _reject_unknown_rule_keys(name: str, body: Mapping[str, Any]) -> None:
    extra = set(body) - _RULE_KEYS
    if extra:
        raise ConfigError(f"rule {name!r} has unknown keys: {sorted(extra)}")


def load_policy(source: str | Path | Mapping[str, Any]) -> Policy:
    if isinstance(source, Mapping):
        data = dict(source)
    else:
        data = json.loads(Path(source).read_text(encoding="utf-8"))
    rules_raw = data.get("rules")
    if not isinstance(rules_raw, dict):
        raise ConfigError("policy must contain a rules object")
    rules: dict[str, Rule] = {}
    for name, body in rules_raw.items():
        if not isinstance(body, dict):
            raise ConfigError(f"rule {name!r} must be an object")
        _reject_unknown_rule_keys(name, body)
        requires = True if "requires_approval" not in body else bool(body["requires_approval"])
        ladder = tuple(str(x) for x in body.get("ladder", ()))
        deadline_s = int(body.get("deadline_s", body.get("deadline_seconds", 0)))
        quorum = int(body.get("quorum", 1))
        if requires:
            on_expiry = _parse_on_expiry(body.get("on_expiry"), f"rules.{name}")
        else:
            on_expiry = OnExpiry.DENY
        rules[name] = Rule(requires, ladder, deadline_s, on_expiry, quorum)
    return Policy(rules)
