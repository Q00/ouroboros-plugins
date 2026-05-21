"""Risk, trust, and confirmation checks for GSD AgentOS invocations."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    missing_scopes: tuple[str, ...] = ()
    confirmation_required: bool = False
    message: str = ""


def trusted_scopes(raw: str | None = None) -> set[str]:
    value = os.environ.get("OUROBOROS_TRUST_SCOPES", "") if raw is None else raw
    return {part.strip() for part in value.replace(";", ",").split(",") if part.strip()}


def required_scopes(command: dict, *, execute: bool) -> list[str]:
    scopes = list(command.get("required_permissions", []))
    if execute and "shell:execute" not in scopes:
        scopes.append("shell:execute")
    if not execute:
        scopes = [scope for scope in scopes if scope != "shell:execute"]
    return scopes


def confirmation_matches(command: dict, confirm: str | bool | None) -> bool:
    if command.get("risk") != "destructive":
        return True
    if confirm is True or confirm == command["canonical_name"]:
        return True
    return os.environ.get("GSD_AGENTOS_CONFIRM") == command["canonical_name"]


def check_policy(
    command: dict,
    *,
    execute: bool = False,
    confirm: str | bool | None = None,
    trust: Iterable[str] | None = None,
) -> PolicyDecision:
    granted = set(trust) if trust is not None else trusted_scopes()
    missing = tuple(scope for scope in required_scopes(command, execute=execute) if scope not in granted)
    if missing:
        grants = " ".join(f"--scope {scope}" for scope in missing)
        return PolicyDecision(
            allowed=False,
            missing_scopes=missing,
            message=(
                f"missing trust scopes for gsd {command['canonical_name']}: {', '.join(missing)}. "
                f"Grant with: ouroboros plugin trust gsd-agentos {grants}"
            ),
        )
    if command.get("risk") == "destructive" and not confirmation_matches(command, confirm):
        return PolicyDecision(
            allowed=False,
            confirmation_required=True,
            message=(
                f"gsd {command['canonical_name']} is destructive/high-impact "
                "and requires explicit confirmation. "
                f"Pass --confirm {command['canonical_name']} after granting trust."
            ),
        )
    return PolicyDecision(allowed=True, message="allowed")
