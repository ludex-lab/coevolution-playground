from __future__ import annotations

from typing import Any, Mapping

from silence_expiry.policy import ConfigError

_RISK_RANK = {"read_only": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}


class EscalationError(ValueError):
    pass


def risk_rank(risk: str) -> int:
    try:
        return _RISK_RANK[risk]
    except KeyError as exc:
        raise ConfigError(f"unknown risk level {risk!r}") from exc


def check_fallbacks(actions: Mapping[str, Mapping[str, Any]]) -> list[str]:
    problems: list[str] = []
    for name, spec in actions.items():
        target = spec.get("safe_fallback")
        if not target:
            continue
        if target not in actions:
            problems.append(f"{name}: fallback {target!r} is not registered")
            continue
        if target == name:
            problems.append(f"{name}: fallback points at itself")
            continue
        if risk_rank(str(actions[target]["risk"])) >= risk_rank(str(spec["risk"])):
            problems.append(f"{name}: fallback {target!r} is not lower risk")
    return problems


def validated_fallback(tool: str, actions: Mapping[str, Mapping[str, Any]]) -> str | None:
    spec = actions.get(tool, {})
    target = spec.get("safe_fallback")
    if not target:
        return None
    for msg in check_fallbacks(actions):
        if msg.startswith(f"{tool}:"):
            raise ConfigError(msg)
    return str(target)
