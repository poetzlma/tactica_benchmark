"""Battle runner. Deterministic given a seed."""

import time
from collections import defaultdict
from random import Random

from . import pathfinding
from .api import UnitView, WorldView
from .types import Team, UnitType, Action
from .unit_specs import UNIT_SPECS
from .world import World, default_map


def _spawn_team(world, team: Team, composition: dict, tactics: dict, anchor: tuple):
    ax, ay = anchor
    direction = 1 if team == Team.RED else -1
    # Spread units in a vertical column near the anchor, expanding outward.
    candidates = []
    for radius in range(0, 30):
        for dy in range(-radius, radius + 1):
            for dx in range(0, radius + 1):
                candidates.append((dx * direction, dy))
    seen = set()
    queue = []
    for c in candidates:
        if c in seen:
            continue
        seen.add(c)
        queue.append(c)
    for utype, count in composition.items():
        for _ in range(count):
            placed = False
            while queue:
                dx, dy = queue.pop(0)
                cell = (ax + dx, ay + dy)
                if not (0 <= cell[0] < world.width and 0 <= cell[1] < world.height):
                    continue
                if cell in world.obstacles:
                    continue
                if cell in world.occupied_cells():
                    continue
                u = world.spawn_unit(utype, team, cell)
                u.tactic = tactics[utype]()
                placed = True
                break
            if not placed:
                raise RuntimeError(f"Could not place {utype} for {team}")


def _resolve(world, unit, action):
    """Return True if the action did something (not idle)."""
    if action is None or not isinstance(action, Action) or action.kind == "hold":
        return False
    me_view = UnitView(unit, world)
    if action.kind == "attack":
        target = world.units.get(action.target_id)
        if not target or not target.alive or target.team == unit.team:
            return False
        if not me_view.can_attack(target):
            return False
        dmg = unit.spec.damage
        target.hp -= dmg
        unit.dmg_dealt += dmg
        target.dmg_taken += dmg
        unit.cooldown = unit.spec.attack_cooldown
        world.frame_events.append({
            "kind": "attack",
            "from_id": unit.id,
            "to_id": target.id,
            "dmg": dmg,
        })
        if target.hp <= 0:
            target.alive = False
            target.death_tick = world.tick
            unit.kills_made += 1
            world.frame_events.append({
                "kind": "kill",
                "killer_id": unit.id,
                "victim_id": target.id,
            })
            world.event_log.append((
                world.tick,
                f"{unit.team.value} {unit.type.value}#{unit.id} killed "
                f"{target.team.value} {target.type.value}#{target.id} at {target.pos}",
            ))
        return True
    if action.kind == "heal":
        target = world.units.get(action.target_id)
        if not target or not target.alive or target.team != unit.team:
            return False
        if not me_view.can_heal(target):
            return False
        heal = unit.spec.heal_amount
        target.hp = min(target.hp + heal, target.spec.max_hp)
        unit.cooldown = unit.spec.attack_cooldown
        world.frame_events.append({
            "kind": "heal",
            "from_id": unit.id,
            "to_id": target.id,
            "amount": heal,
        })
        return True
    if action.kind == "move":
        if unit.move_cd > 0:
            return False
        dest = action.target_pos
        if not dest:
            return False
        dest = (int(dest[0]), int(dest[1]))
        occupied = world.occupied_cells() - {unit.pos}
        path = pathfinding.a_star(
            unit.pos, dest, world.width, world.height,
            world.obstacles, occupied,
        )
        if not path or len(path) < 2:
            return False
        next_cell = path[1]
        if next_cell in world.occupied_cells():
            return False
        unit.pos = next_cell
        unit.move_cd = unit.spec.move_period
        return True
    return False


def _new_stats():
    return {
        "crashes": 0,
        "timeouts": 0,
        "per_type": defaultdict(lambda: {
            "started": 0, "killed": 0, "kills_made": 0,
            "dmg_dealt": 0, "dmg_taken": 0,
            "lifespan_sum": 0, "idle_sum": 0,
            "crashes": 0, "timeouts": 0,
        }),
    }


def run_battle(
    comp_red, tactics_red,
    comp_blue, tactics_blue,
    seed=42, max_ticks=1200, on_frame=None,
    tick_budget_ms=50,
):
    rng = Random(seed)
    world = World(map=default_map(), rng=rng)

    _spawn_team(world, Team.RED, comp_red, tactics_red, world.map.red_spawn)
    _spawn_team(world, Team.BLUE, comp_blue, tactics_blue, world.map.blue_spawn)

    stats = {Team.RED: _new_stats(), Team.BLUE: _new_stats()}
    for u in world.units.values():
        stats[u.team]["per_type"][u.type]["started"] += 1

    final_tick = 0
    for tick in range(max_ticks):
        world.tick = tick
        final_tick = tick
        world.frame_events = []

        red_alive = world.count_alive(Team.RED)
        blue_alive = world.count_alive(Team.BLUE)
        if red_alive == 0 or blue_alive == 0:
            break

        for u in world.units.values():
            if not u.alive:
                continue
            if u.cooldown > 0:
                u.cooldown -= 1
            if u.move_cd > 0:
                u.move_cd -= 1

        actions = []
        for uid in sorted(world.units.keys()):
            u = world.units[uid]
            if not u.alive:
                continue
            me_view = UnitView(u, world)
            world_view = WorldView(u, world)
            start = time.perf_counter()
            try:
                action = u.tactic.tick(me_view, world_view)
            except Exception as e:
                u.crashes += 1
                stats[u.team]["crashes"] += 1
                stats[u.team]["per_type"][u.type]["crashes"] += 1
                world.event_log.append((
                    tick,
                    f"{u.team.value} {u.type.value}#{u.id} crashed: "
                    f"{type(e).__name__}: {e}",
                ))
                action = None
            elapsed_ms = (time.perf_counter() - start) * 1000
            if elapsed_ms > tick_budget_ms:
                u.timeouts += 1
                stats[u.team]["timeouts"] += 1
                stats[u.team]["per_type"][u.type]["timeouts"] += 1
            actions.append((u, action))

        for u, action in actions:
            if not u.alive:
                continue
            took = _resolve(world, u, action)
            if not took:
                u.idle_ticks += 1

        if on_frame:
            on_frame(world, tick)

    # Aggregate per-unit stats into per-type rollups
    for u in world.units.values():
        bucket = stats[u.team]["per_type"][u.type]
        bucket["kills_made"] += u.kills_made
        bucket["dmg_dealt"] += u.dmg_dealt
        bucket["dmg_taken"] += u.dmg_taken
        bucket["idle_sum"] += u.idle_ticks
        if not u.alive:
            bucket["killed"] += 1
            bucket["lifespan_sum"] += (u.death_tick or final_tick) - u.spawn_tick
        else:
            bucket["lifespan_sum"] += final_tick - u.spawn_tick

    red_alive = world.count_alive(Team.RED)
    blue_alive = world.count_alive(Team.BLUE)
    red_value = world.surviving_value(Team.RED)
    blue_value = world.surviving_value(Team.BLUE)

    if red_alive == 0 and blue_alive == 0:
        outcome = "draw"
    elif red_alive == 0:
        outcome = "blue_win"
    elif blue_alive == 0:
        outcome = "red_win"
    else:
        if red_value > blue_value:
            outcome = "red_win_timeout"
        elif blue_value > red_value:
            outcome = "blue_win_timeout"
        else:
            outcome = "draw_timeout"

    return {
        "outcome": outcome,
        "duration_ticks": final_tick + 1,
        "red_alive": red_alive,
        "blue_alive": blue_alive,
        "red_survivors_value": red_value,
        "blue_survivors_value": blue_value,
        "stats": stats,
        "event_log": world.event_log,
    }
