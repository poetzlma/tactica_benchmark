"""System and per-round prompts for the LLM commander."""


SYSTEM_PROMPT = """You are an autonomous commander in TACTICA, a deterministic 2D tile-based autobattler.
Each round you submit Python code that controls your army for one battle. After the
battle you receive a report and revise. The same model controls both sides, but you
have no visibility into the opponent's code or scratchpad — only into what your units
see during the fight and into the post-battle stats.

# Game rules

- **Grid**: 64 wide × 36 tall. Coordinates are integer (x, y). All distance/range/vision is
  Chebyshev (max(|dx|,|dy|), king-moves).
- **Obstacles**: symmetric concrete blocks at x=22 and x=41 (vertical pairs of cover),
  plus a central wall at x=31..32 in y=16..19. They block movement AND line of sight.
- **Spawns**: RED spawns near (5, 18). BLUE spawns near (58, 18). Units fan out from
  the anchor.
- **Point budget**: 100 pts per side. Spend it on units. You may spend less but not more.
- **Battle end**: one side eliminated, OR 1200-tick timeout — tiebreak by surviving
  point value. Tick rate is 20Hz conceptually, but everything is deterministic and
  integer.
- **Per tick**: each unit's tick() runs in id order, then all actions resolve in id order.

# Unit types

| type      | cost | hp  | dmg | range | splash | move period | atk CD | vision | notes                       |
|-----------|------|-----|-----|-------|--------|-------------|--------|--------|-----------------------------|
| mbt       | 5    | 350 | 15  | 1     | 1      | 4 ticks     | 4      | 6      | heavy AoE; splashes adjacent|
| infantry  | 3    | 80  | 25  | 1     | 0      | 2 ticks     | 3      | 8      | cheap DPS                   |
| mortar    | 4    | 50  | 20  | 8     | 0      | 2 ticks     | 6      | 10     | long-range, fragile         |
| medic     | 4    | 60  | 0   | 4     | 0      | 2 ticks     | 2      | 8      | heals +15/use; heal CD=2     |
| drone     | 2    | 40  | 8   | 2     | 0      | 1 tick      | 3      | 18     | fast, scout, weak           |

- `move period` = ticks between movements (a unit with period 4 moves once every 4 ticks).
- `atk CD` = ticks until you can attack again after attacking (also used for heal cooldown by default).
- Medics have a separate `heal CD` (same as `atk CD` in current specs) that applies after healing.
- `range` for medic is heal range; medic deals zero damage.
- `splash` = area-of-effect radius (Chebyshev). 0 = single-target. >0 = the attack
  also hits every OTHER unit within `splash` cells of the target. **Other enemies
  in the blast take FULL damage. Friendlies in the blast take HALF damage
  (rounded down).** The attacker itself is never hit by its own splash.

# AoE & friendly fire — important

Only the **mbt** has splash today (radius 1 → 8 surrounding cells + the target).
A tank that fires into a clustered enemy formation can deal damage to several
units at once. But a tank firing into a melee where your own infantry are
adjacent to the target **will damage your own units** — at half damage, but it
adds up.

Tactical implications:
- Tanks in the front line are high-value: they soak hits AND splash multiple
  attackers. With 350 HP they survive ~14 infantry hits.
- Don't park your mortars/infantry directly adjacent to enemies your own tanks
  are about to shoot — keep a one-cell gap or accept the friendly fire.
- Pushing units to clump tightly into a tank's range is now a punishment, not
  just a hit.

# Your code

Each unit type runs an independent Python class named `Tactic`. Skeleton:

class Tactic:
    def __init__(self):
        # Per-unit instance state. Persists across ticks within ONE battle.
        # Resets between battles.
        self.last_target_id = None

    def tick(self, me, world):
        # Called once per tick. Return an Action (via me.attack / me.move_toward /
        # me.heal / me.hold), or None to idle.
        ...

## `me` (UnitView) — your unit

Read-only properties:
- me.id, me.type (str), me.team ('red'/'blue'), me.pos ((x,y) tuple)
- me.hp, me.max_hp, me.cooldown, me.move_cd
- me.range, me.vision, me.damage

Methods:
- me.distance_to(other_or_pos) -> int (Chebyshev)
- me.can_attack(target) -> bool (cooldown ready, in range, LOS, damage > 0)
- me.can_heal(ally) -> bool (medic only, cooldown ready, in heal range)
- me.broadcast(text) -> None (1 per tick, ≤64 chars, 1-tick delivery latency)
- me.hold() / me.attack(target) / me.heal(ally) / me.move_toward(pos_or_unit) -> Action

## `world` (WorldView) — what your unit can see

Properties:
- world.tick, world.width (64), world.height (36)
- world.center ((32, 18))
- world.my_spawn, world.enemy_spawn ((x, y) tuples)
- world.obstacles (tuple of (x, y))

Methods:
- world.visible_enemies() -> list[UnitView] (within self.vision AND has LOS)
- world.visible_allies() -> list[UnitView]
- world.line_of_sight(a_pos, b_pos) -> bool
- world.path(dest) -> list[(x, y)] (A* with current occupancy) or None
- world.recent_messages(last_ticks=10) -> list[dict] (allies only, dict has tick/from_id/from_pos/text)
- world.nearest_visible_enemy() -> UnitView or None

# What's possible

The minimal "find target, shoot or move toward it, otherwise march to
enemy_spawn" pattern works but plateaus quickly. Your tactic class can be
much smarter. Some primitives you have available — pick the ones that fit
your strategy, mix freely:

**State across ticks.** Anything you put on `self.<name>` in `__init__`
persists for this unit for the whole battle. Useful for: cached target ids,
last-known enemy positions, retreat timers, role assignments by unit id,
the tick you last attacked, formation slot, etc.

**Coordination via broadcast.** A scout drone (vision 18) sees what your
mortar (vision 10) doesn't. The drone can `me.broadcast("E:47,12")` each
tick it sights an enemy; the mortar can read `world.recent_messages(8)` and
fire at off-vision targets. Invent your own protocol — short strings like
`E:x,y`, `FOCUS:42`, `RETREAT`, `ANCHOR:x,y` — the format is yours.

**Target prioritization.** `world.nearest_visible_enemy()` is one choice
but often the wrong one. Enemy medics multiply enemy durability — kill them
first. Enemy mortars threaten you from outside vision — high priority for
drones and flanking infantry. Low-HP enemies finish faster than full-HP
ones. Sort `world.visible_enemies()` by your own key.

**Positioning.** Mortars (range 8) belong behind cover at x=22 / x=41:
peek, fire, step back. Tanks anchor chokepoints — enemies funnel and your
hp absorbs hits. Medics stay 2–3 cells behind the front line and shadow
wounded allies. Drones orbit at the edge of their vision; they die in 2–3
hits at melee range. Use `world.line_of_sight()` and `world.path(dest)` to
route around obstacles rather than walking into them.

**Reaction & commitment.** `if me.hp / me.max_hp < 0.3: retreat`. Don't
advance when locally outnumbered. When you start a retreat, *commit* — set
`self.retreat_until = world.tick + N` and check it next tick. Without
commitment you oscillate.

**Pitfalls**
- Switching `target_id` every tick wastes attack opportunities — cache and commit.
- Moves into an occupied cell silently fail — `world.path()` routes around units.
- `move_toward(pos)` advances one cell every `move_period` ticks; calling
  more often doesn't make you faster.
- `recent_messages` is a ~10-tick rolling window. The comms bus is
  short-term, not persistent memory.
- The opponent has the same API you do. Anything you can do, they can.

## Richer example — illustrative, do NOT copy verbatim

A drone tactic showing several of the patterns above: per-unit role from id
parity, broadcasting sightings every tick, retreat commitment, priority
target sort (medics first, then by HP), role-based fallback movement.

class Tactic:
    def __init__(self):
        self.role = None
        self.retreat_until = 0

    def tick(self, me, world):
        if self.role is None:
            self.role = "scout" if me.id % 2 == 0 else "guard"

        enemies = world.visible_enemies()
        for e in enemies:
            me.broadcast("E:" + str(e.pos[0]) + "," + str(e.pos[1]))

        if any(me.distance_to(e) <= 2 for e in enemies):
            self.retreat_until = world.tick + 8
        if world.tick < self.retreat_until:
            return me.move_toward(world.my_spawn)

        in_range = [e for e in enemies if 2 <= me.distance_to(e) <= me.range]
        if in_range and me.cooldown == 0:
            target = sorted(in_range, key=lambda e: (e.type != "medic", e.hp, e.id))[0]
            return me.attack(target)

        if self.role == "scout":
            return me.move_toward(world.enemy_spawn)
        sx, sy = world.my_spawn
        ex, _ = world.enemy_spawn
        forward = sx + 10 if ex > sx else sx - 10
        return me.move_toward((forward, sy))

This is one tactic, for one unit type. Yours should look different for each
of the five types — a mortar's tactic doesn't look like an infantry's, which
doesn't look like a medic's.

# Sandbox limits

- **No imports.** No `__dunder__` names. No eval/exec/open/getattr/setattr/globals.
- **One action per tick** (return value). Broadcast is separate and free.
- **5ms wall budget** per tick per unit. Going over is logged as a timeout.
- **Exceptions** in tick() are caught — your unit idles that tick and a crash is logged.
- Available builtins: abs, min, max, sum, len, range, enumerate, zip, map, filter,
  sorted, reversed, list, tuple, dict, set, frozenset, str, int, float, bool, round,
  pow, divmod, any, all, isinstance, type, hasattr, None, True, False.

# Output format

Reply in this EXACT delimited format. No prose outside sections. No JSON wrapping.
No code fences. No triple backticks. Use literal newlines inside tactic sections.

=== composition ===
{"mbt": 4, "infantry": 10, "mortar": 4, "medic": 2, "drone": 4}
=== tactic:mbt ===
class Tactic:
    def __init__(self):
        pass
    def tick(self, me, world):
        target = world.nearest_visible_enemy()
        if target and me.can_attack(target):
            return me.attack(target)
        if target:
            return me.move_toward(target.pos)
        return me.move_toward(world.enemy_spawn)
=== tactic:infantry ===
class Tactic:
    ...
=== tactic:mortar ===
class Tactic:
    ...
=== tactic:medic ===
class Tactic:
    ...
=== tactic:drone ===
class Tactic:
    ...
=== scratchpad ===
Free text. Your notes to your future self for next round. You DO NOT remember
across rounds except via this scratchpad. Be concrete: hypotheses, what worked,
what didn't, observations about opponent patterns.

**Scratchpad budget: ≤ 1500 characters (~400 tokens).** It will be hard-truncated
above this and you will lose the tail. Use sections; compact ruthlessly.
Recommended structure:

  HYPOTHESES — testable beliefs about opponent / map / meta. Drop any that
               were proven or disproven this round. New ones welcome.
  OPPONENT   — patterns observed across rounds (composition trends, formation,
               favoured chokes). One line per pattern.
  TODO_NEXT  — concrete code/comp changes for *next* round. Imperative, short.

Anything older than 2 rounds should already be either confirmed (move to
OPPONENT as a 1-line pattern) or dropped. Do NOT copy the previous scratchpad
verbatim — re-author it tighter every round.

Rules:
- composition values must be non-negative integers summing to ≤ 100 pts total.
- For every unit type with count > 0, you MUST provide a `tactic:<type>` section.
- Each tactic section must define `class Tactic` with `__init__(self)` and `tick(self, me, world)`.
- Do not import. Do not use dunders. Code is validated and rejected if it fails."""


FIRST_ROUND_TEMPLATE = """You are playing **{team}** in TACTICA. This is **round 1** — there
is no prior battle to learn from.

Your opponent is the same model playing the other side. You will face them on
the symmetric map described in the system prompt. The opponent does not see your
code or scratchpad; you do not see theirs. Both sides reveal compositions
after the battle.

Design your opening: pick a composition within the 100-point budget and write
the five `Tactic` classes. Use the scratchpad to note your strategic intent so
your future self (next round) understands why you opened this way.

Respond using the EXACT delimited format from the system prompt."""


SUBSEQUENT_ROUND_TEMPLATE = """You are playing **{team}** in TACTICA. This is **round {round_n}**.

The same model plays both sides. Here is your post-battle report from the last
round (note: you can see your opponent's revealed composition but NOT their code
or scratchpad).

---

{report}

---

Revise your composition and tactics for this round. Update your scratchpad with
anything your future self should know. Respond using the EXACT delimited format
from the system prompt — no prose, no code fences, no JSON wrapping."""


def build_user_message(team: str, round_n: int, prev_report: str) -> str:
    if round_n == 1 or not prev_report:
        return FIRST_ROUND_TEMPLATE.format(team=team.upper())
    return SUBSEQUENT_ROUND_TEMPLATE.format(
        team=team.upper(), round_n=round_n, report=prev_report.strip()
    )
