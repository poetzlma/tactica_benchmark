"""Post-round report generator.

Produces the markdown summary a team sees as input to its next round of
code-writing. The same text is shown in the observer UI's "Report" tab.

A report includes both teams' compositions (you do see opponent's
composition after the battle) but NOT the opponent's code or scratchpad.
"""

from .types import Team, UnitType
from .unit_specs import UNIT_SPECS

# 7-level ramp for nonzero bins, low → high. Empty bins use '.' below.
HEATMAP_RAMP = ":-+*#%@"
HEATMAP_BIN_W = 4  # 64 / 4 = 16 cols
HEATMAP_BIN_H = 4  # 36 / 4 = 9 rows


def _downsample(grid_flat, src_w, src_h, bin_w, bin_h):
    out_w = (src_w + bin_w - 1) // bin_w
    out_h = (src_h + bin_h - 1) // bin_h
    out = [[0] * out_w for _ in range(out_h)]
    for y in range(src_h):
        for x in range(src_w):
            v = grid_flat[y * src_w + x]
            if v:
                out[y // bin_h][x // bin_w] += v
    return out, out_w, out_h


def _render_heatmap(title, grid_flat, src_w, src_h):
    binned, w, h = _downsample(grid_flat, src_w, src_h, HEATMAP_BIN_W, HEATMAP_BIN_H)
    peak = max((max(row) for row in binned), default=0)
    if peak == 0:
        return [f"### {title}", "(no activity)"]
    lines = [f"### {title}", f"_{w}×{h} bins, each bin = {HEATMAP_BIN_W}×{HEATMAP_BIN_H} cells; peak={peak}_", "```"]
    # Header: x-axis labels every other column
    header = "  " + "".join(str((c * HEATMAP_BIN_W) // 10 % 10) if c % 2 == 0 else " " for c in range(w))
    lines.append(header)
    for r, row in enumerate(binned):
        chars = []
        for v in row:
            if v == 0:
                chars.append(".")
            else:
                idx = min(len(HEATMAP_RAMP) - 1, int(v / peak * (len(HEATMAP_RAMP) - 1) + 0.5))
                chars.append(HEATMAP_RAMP[idx])
        y_label = f"{(r * HEATMAP_BIN_H):2d}"
        lines.append(f"{y_label} {''.join(chars)}")
    lines.append("```")
    return lines


def _outcome_for(team: str, outcome: str) -> str:
    if outcome == "draw" or outcome == "draw_timeout":
        return "DRAW"
    if outcome.startswith(team):
        return "WIN"
    return "LOSS"


def _composition_block(comp: dict) -> list:
    lines = []
    total = 0
    for utype_str, count in comp.items():
        cost = UNIT_SPECS[UnitType(utype_str)].cost
        line_cost = cost * count
        total += line_cost
        lines.append(f"- {utype_str}: {count} × {cost} = {line_cost} pts")
    lines.append(f"- **Total: {total} pts**")
    return lines


def _stats_table(team_stats: dict) -> list:
    lines = [
        "| Type | Start | Lost | Kills | Dmg out | Dmg in | Avg life | Idle % | Crash |",
        "|------|-------|------|-------|---------|--------|----------|--------|-------|",
    ]
    for utype, pt in team_stats["per_type"].items():
        avg_life = (pt["lifespan_sum"] / pt["started"]) if pt["started"] else 0
        idle_pct = (pt["idle_sum"] / pt["lifespan_sum"] * 100) if pt["lifespan_sum"] else 0
        lines.append(
            f"| {utype.value} | {pt['started']} | {pt['killed']} | "
            f"{pt['kills_made']} | {pt['dmg_dealt']} | {pt['dmg_taken']} | "
            f"{avg_life:.0f}t | {idle_pct:.0f}% | {pt['crashes']} |"
        )
    return lines


def generate_report(team: str, result: dict, my_brief, opp_brief, heatmaps: dict = None) -> str:
    team_enum = Team.RED if team == "red" else Team.BLUE
    opp = "blue" if team == "red" else "red"

    my_value = result[f"{team}_survivors_value"]
    opp_value = result[f"{opp}_survivors_value"]
    my_alive = result[f"{team}_alive"]
    opp_alive = result[f"{opp}_alive"]
    outcome_label = _outcome_for(team, result["outcome"])

    lines = []
    lines.append(f"# Round {my_brief.round} report — {team.upper()}")
    lines.append("")
    lines.append("## Outcome")
    lines.append(f"- Result: **{outcome_label}** ({result['outcome']})")
    lines.append(f"- Duration: {result['duration_ticks']} ticks")
    lines.append(f"- Your survivors: {my_alive} units, {my_value} pts of value")
    lines.append(f"- Their survivors: {opp_alive} units, {opp_value} pts of value")
    lines.append("")

    lines.append("## Your composition")
    lines.extend(_composition_block(my_brief.composition))
    lines.append("")

    lines.append("## Opponent's revealed composition")
    lines.extend(_composition_block(opp_brief.composition))
    lines.append("")

    lines.append("## Per-unit-type performance (your side)")
    lines.extend(_stats_table(result["stats"][team_enum]))
    lines.append("")

    crashes = result["stats"][team_enum]["crashes"]
    timeouts = result["stats"][team_enum]["timeouts"]
    if crashes or timeouts:
        lines.append("## Code health")
        lines.append(
            f"- Crashes: {crashes}   Timeouts: {timeouts}"
        )
        lines.append("- Your code raised exceptions or exceeded the tick budget. "
                     "Check the events below and fix the offending tactic.")
        lines.append("")

    lines.append("## Key events (last 25, chronological)")
    tail = result["event_log"][-25:]
    if tail:
        for tick, msg in tail:
            lines.append(f"- t={tick}: {msg}")
    else:
        lines.append("- (no kills logged — likely a stalemate)")
    lines.append("")

    if heatmaps:
        lines.append("## Spatial recap")
        lines.append(
            "Where things happened on the 64×36 grid. "
            "Bins shown are 4×4 cells. Y grows downward. "
            "Density: `.` empty → `:-+*#%@` increasing. "
            "RED spawns at the LEFT (~x=5); BLUE spawns at the RIGHT (~x=58). "
            "The `peak` is the count in the busiest bin — use it to gauge magnitude."
        )
        lines.append("")
        w = heatmaps.get("width", 64)
        h = heatmaps.get("height", 36)
        my_deaths = heatmaps.get("deaths", {}).get(team, [])
        my_dmg = heatmaps.get("damage_dealt", {}).get(team, [])
        opp_presence = heatmaps.get("presence", {}).get(opp, [])
        if my_deaths:
            lines.extend(_render_heatmap("Where YOUR units died", my_deaths, w, h))
            lines.append("")
        if my_dmg:
            lines.extend(_render_heatmap("Where YOU dealt damage from", my_dmg, w, h))
            lines.append("")
        if opp_presence:
            lines.extend(_render_heatmap("Where the ENEMY spent time (unit-ticks)", opp_presence, w, h))
            lines.append("")

    lines.append("## Your scratchpad from last round")
    sp = my_brief.scratchpad.strip()
    if sp:
        lines.append("```")
        lines.append(sp)
        lines.append("```")
    else:
        lines.append("_(empty — this was your first round, or you wrote nothing)_")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("Write your next round: revise tactics, adjust composition, "
                 "update your scratchpad with anything your future self should know.")

    return "\n".join(lines)
