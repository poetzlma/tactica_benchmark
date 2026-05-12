"""CLI entry point. Runs a single battle (or two for the determinism check)."""

import argparse
import sys

from . import tactics_builtin as T
from .battle import run_battle
from .brief import TeamBrief
from .recorder import Recorder, dump_json
from .render import render_ascii
from .report import generate_report
from .sandbox import load_tactic
from .types import Team, UnitType
from .unit_specs import UNIT_SPECS


RUSH_REASONING = (
    "Strategy: aggressive rush. Close to engagement range fast; ignore "
    "positioning niceties. Infantry forms the bulk because they have the best "
    "DPS-per-cost. A handful of mortars provide opportunistic damage but I "
    "expect them to die when the lines collide. Drones scout and harass. "
    "One medic to keep the MBT line alive on the way in."
)

TURTLE_REASONING = (
    "Strategy: defensive turtle behind cover. MBT line anchors a ~6-cell "
    "advance from spawn and holds. Mortars from behind the wall blocks deal "
    "damage from outside the enemy's effective range. Medics hold close to "
    "the MBTs. Drones are minimal — turret/range advantage wins this."
)


def build_brief(team: str, style: str, round_num: int = 1) -> TeamBrief:
    """Construct a TeamBrief for the hardcoded sides used in the prototype."""
    if style == "rush":
        comp = {
            "mbt": 3, "infantry": 8, "mortar": 2,
            "medic": 1, "drone": 4,
        }
        base = T.AGGRESSIVE_RUSH
        reasoning = RUSH_REASONING
    else:
        comp = {
            "mbt": 5, "infantry": 5, "mortar": 4,
            "medic": 2, "drone": 2,
        }
        base = T.DEFENSIVE_TURTLE
        reasoning = TURTLE_REASONING

    tactics = {
        "mbt": base,
        "infantry": base,
        "mortar": base,
        "medic": T.MEDIC_TACTIC,
        "drone": T.DRONE_SCOUT,
    }
    return TeamBrief(
        round=round_num,
        team=team,
        model=f"hardcoded:{style}",
        reasoning=reasoning,
        composition=comp,
        tactics=tactics,
        scratchpad="",
    )


def brief_to_classes(brief: TeamBrief):
    return {
        UnitType(utype_str): load_tactic(src, f"{brief.team}_{utype_str}")
        for utype_str, src in brief.tactics.items()
    }


def brief_to_comp_enum(brief: TeamBrief):
    return {UnitType(k): v for k, v in brief.composition.items()}


def composition_cost(comp_str: dict):
    return sum(UNIT_SPECS[UnitType(k)].cost * v for k, v in comp_str.items())


def print_result(r):
    print(f"\nOutcome: {r['outcome']}")
    print(f"Duration: {r['duration_ticks']} ticks")
    print(
        f"Red alive: {r['red_alive']} (value {r['red_survivors_value']})   "
        f"Blue alive: {r['blue_alive']} (value {r['blue_survivors_value']})"
    )
    print("\nPer-team / per-unit stats:")
    for team, ts in r["stats"].items():
        print(
            f"  {team.value.upper()}: "
            f"crashes={ts['crashes']} timeouts={ts['timeouts']}"
        )
        for utype, pt in ts["per_type"].items():
            avg_life = (pt["lifespan_sum"] / pt["started"]) if pt["started"] else 0.0
            print(
                f"    {utype.value:9s}  "
                f"started={pt['started']:3d}  killed={pt['killed']:3d}  "
                f"kills={pt['kills_made']:3d}  "
                f"dmg_dealt={pt['dmg_dealt']:5d}  dmg_taken={pt['dmg_taken']:5d}  "
                f"avg_life={avg_life:6.1f}t  idle={pt['idle_sum']}"
            )


def main(argv=None):
    parser = argparse.ArgumentParser(description="Tactica prototype runner")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-ticks", type=int, default=1200)
    parser.add_argument(
        "--render-every", type=int, default=0,
        help="Print ASCII frame every N ticks (0 = off)",
    )
    parser.add_argument(
        "--determinism-check", action="store_true",
        help="Run twice with the same seed and verify identical outcome",
    )
    parser.add_argument(
        "--record", type=str, default=None,
        help="If set, write a JSON replay of the battle to this path",
    )
    args = parser.parse_args(argv)

    red_brief = build_brief("red", "rush")
    blue_brief = build_brief("blue", "turtle")

    print(f"Red (rush)    composition cost: {composition_cost(red_brief.composition)}")
    print(f"Blue (turtle) composition cost: {composition_cost(blue_brief.composition)}")

    def run(seed, recorder_box=None):
        callbacks = []
        if args.render_every:
            def render_cb(world, tick):
                if tick % args.render_every == 0:
                    print(f"\n--- Tick {tick} ---")
                    print(render_ascii(world))
            callbacks.append(render_cb)

        if recorder_box is not None:
            def record_cb(world, tick):
                if recorder_box[0] is None:
                    recorder_box[0] = Recorder(
                        world,
                        red_brief=red_brief,
                        blue_brief=blue_brief,
                        seed=seed,
                    )
                recorder_box[0].snapshot()
            callbacks.append(record_cb)

        if callbacks:
            def on_frame(world, tick):
                for cb in callbacks:
                    cb(world, tick)
        else:
            on_frame = None

        return run_battle(
            comp_red=brief_to_comp_enum(red_brief),
            tactics_red=brief_to_classes(red_brief),
            comp_blue=brief_to_comp_enum(blue_brief),
            tactics_blue=brief_to_classes(blue_brief),
            seed=seed, max_ticks=args.max_ticks, on_frame=on_frame,
        )

    print(f"\n=== Battle (seed={args.seed}) ===")
    recorder_box = [None] if args.record else None
    r1 = run(args.seed, recorder_box=recorder_box)
    print_result(r1)

    if args.record:
        rec = recorder_box[0]
        heatmaps = rec.compute_heatmaps()
        red_report = generate_report("red", r1, red_brief, blue_brief, heatmaps=heatmaps)
        blue_report = generate_report("blue", r1, blue_brief, red_brief, heatmaps=heatmaps)
        data = rec.finalize(r1, red_report=red_report, blue_report=blue_report,
                            heatmaps=heatmaps)
        dump_json(data, args.record)
        print(f"\nRecording written: {args.record} ({len(rec.frames)} frames)")

    if args.determinism_check:
        print("\n=== Re-running with same seed ===")
        r2 = run(args.seed)
        keys = ("outcome", "duration_ticks",
                "red_alive", "blue_alive",
                "red_survivors_value", "blue_survivors_value")
        match = all(r1[k] == r2[k] for k in keys)
        print(f"\nDeterminism check ({', '.join(keys)}): "
              f"{'PASS' if match else 'FAIL'}")
        if not match:
            for k in keys:
                if r1[k] != r2[k]:
                    print(f"  {k}: {r1[k]!r} vs {r2[k]!r}")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
