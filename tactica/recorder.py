"""Battle recorder: snapshots each tick into a JSON-serializable dict."""

import json

from .unit_specs import UNIT_SPECS
from .types import UnitType


class Recorder:
    def __init__(self, world, red_brief, blue_brief, seed):
        self.world = world
        self.seed = seed
        self.red_brief = red_brief
        self.blue_brief = blue_brief
        spec_dump = {}
        for utype, spec in UNIT_SPECS.items():
            spec_dump[utype.value] = {
                "cost": spec.cost,
                "max_hp": spec.max_hp,
                "damage": spec.damage,
                "range": spec.range,
                "move_period": spec.move_period,
                "attack_cooldown": spec.attack_cooldown,
                "vision": spec.vision,
                "can_heal": spec.can_heal,
                "heal_amount": spec.heal_amount,
            }
        self.header = {
            "version": 1,
            "seed": seed,
            "round": red_brief.round,
            "map": {
                "width": world.width,
                "height": world.height,
                "obstacles": sorted([list(p) for p in world.obstacles]),
                "red_spawn": list(world.map.red_spawn),
                "blue_spawn": list(world.map.blue_spawn),
            },
            "unit_specs": spec_dump,
            "briefs": {
                "red": red_brief.to_dict(),
                "blue": blue_brief.to_dict(),
            },
            "unit_index": [
                {
                    "id": u.id,
                    "type": u.type.value,
                    "team": u.team.value,
                    "max_hp": u.spec.max_hp,
                }
                for u in sorted(world.units.values(), key=lambda x: x.id)
            ],
        }
        self.frames = []

    def snapshot(self):
        units = []
        for u in sorted(self.world.units.values(), key=lambda x: x.id):
            if not u.alive:
                continue
            units.append([u.id, u.pos[0], u.pos[1], u.hp])
        self.frames.append({
            "t": self.world.tick,
            "units": units,
            "events": list(self.world.frame_events),
        })

    def finalize(self, result, red_report=None, blue_report=None):
        stats_dump = {}
        for team, ts in result["stats"].items():
            stats_dump[team.value] = {
                "crashes": ts["crashes"],
                "timeouts": ts["timeouts"],
                "per_type": {
                    ut.value: dict(pt) for ut, pt in ts["per_type"].items()
                },
            }
        return {
            **self.header,
            "frames": self.frames,
            "outcome": result["outcome"],
            "duration_ticks": result["duration_ticks"],
            "red_alive": result["red_alive"],
            "blue_alive": result["blue_alive"],
            "red_survivors_value": result["red_survivors_value"],
            "blue_survivors_value": result["blue_survivors_value"],
            "stats": stats_dump,
            "event_log": [[t, msg] for (t, msg) in result["event_log"]],
            "reports": {
                "red": red_report or "",
                "blue": blue_report or "",
            },
        }


def dump_json(data, path):
    with open(path, "w") as f:
        json.dump(data, f, separators=(",", ":"))
