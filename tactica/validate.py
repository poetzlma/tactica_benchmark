"""Validate a parsed LLM brief: composition arithmetic, tactic sandbox-loadability."""

from .parse import VALID_UTYPES
from .sandbox import SandboxError, load_tactic
from .types import UnitType
from .unit_specs import UNIT_SPECS


POINT_BUDGET = 100


def validate_brief(parsed: dict) -> tuple:
    """Returns (ok, errors). Errors is a list of human-readable strings the
    LLM should be able to fix on a retry."""
    errors = []

    comp = parsed.get("composition")
    if not isinstance(comp, dict) or not comp:
        return False, ["composition is missing or empty"]

    total = 0
    cleaned_comp = {}
    for ut, count in comp.items():
        ut = ut.lower()
        if ut not in VALID_UTYPES:
            errors.append(f"composition has unknown unit type: {ut!r}")
            continue
        if not isinstance(count, int):
            errors.append(f"composition[{ut!r}] must be an integer, got {type(count).__name__}")
            continue
        if count < 0:
            errors.append(f"composition[{ut!r}] must be non-negative, got {count}")
            continue
        cleaned_comp[ut] = count
        cost = UNIT_SPECS[UnitType(ut)].cost
        total += cost * count

    if total > POINT_BUDGET:
        errors.append(
            f"composition costs {total} pts > {POINT_BUDGET} budget — reduce unit counts"
        )
    if total == 0:
        errors.append("composition is empty (sum is 0); you must field at least one unit")

    tactics = parsed.get("tactics") or {}
    for ut, count in cleaned_comp.items():
        if count > 0 and ut not in tactics:
            errors.append(f"composition wants {count} {ut} but no `tactic:{ut}` section provided")

    for ut, src in tactics.items():
        if ut not in VALID_UTYPES:
            errors.append(f"unknown tactic section: tactic:{ut}")
            continue
        if not src.strip():
            errors.append(f"tactic:{ut} is empty")
            continue
        try:
            load_tactic(src, f"validate_{ut}")
        except SandboxError as e:
            errors.append(f"tactic:{ut} rejected by sandbox: {e}")

    # Normalize parsed composition back
    parsed["composition"] = cleaned_comp

    return (len(errors) == 0), errors
