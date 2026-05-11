"""Views passed into Tactic.tick(me, world). Read-only properties + action constructors."""

from .types import Action, Team
from . import pathfinding


class UnitView:
    def __init__(self, unit, world):
        self._unit = unit
        self._world = world

    @property
    def id(self):
        return self._unit.id

    @property
    def type(self):
        return self._unit.type.value

    @property
    def team(self):
        return self._unit.team.value

    @property
    def pos(self):
        return self._unit.pos

    @property
    def hp(self):
        return self._unit.hp

    @property
    def max_hp(self):
        return self._unit.spec.max_hp

    @property
    def cooldown(self):
        return self._unit.cooldown

    @property
    def move_cd(self):
        return self._unit.move_cd

    @property
    def range(self):
        return self._unit.spec.range

    @property
    def vision(self):
        return self._unit.spec.vision

    @property
    def damage(self):
        return self._unit.spec.damage

    def distance_to(self, other_or_pos):
        if hasattr(other_or_pos, "pos"):
            p = other_or_pos.pos
        else:
            p = tuple(other_or_pos)
        return max(abs(self.pos[0] - p[0]), abs(self.pos[1] - p[1]))

    def can_attack(self, other):
        if self.cooldown > 0:
            return False
        if self.damage == 0:
            return False
        d = self.distance_to(other)
        if d > self.range or d < 1:
            return False
        return pathfinding.line_of_sight(
            self.pos, other.pos, self._world.obstacles
        )

    def can_heal(self, ally):
        if not self._unit.spec.can_heal:
            return False
        if not hasattr(ally, "team") or ally.team != self.team:
            return False
        if self._unit.cooldown > 0:
            return False
        return self.distance_to(ally) <= self._unit.spec.range

    def broadcast(self, text):
        from .world import Message

        msg = str(text)[:64]
        self._world.messages.append(
            Message(
                tick=self._world.tick,
                unit_id=self.id,
                team=self._unit.team,
                pos=self.pos,
                text=msg,
            )
        )
        self._world.frame_events.append({
            "kind": "msg",
            "from_id": self.id,
            "text": msg,
        })

    def hold(self):
        return Action(kind="hold")

    def attack(self, target):
        tid = target.id if hasattr(target, "id") else int(target)
        return Action(kind="attack", target_id=tid)

    def heal(self, ally):
        tid = ally.id if hasattr(ally, "id") else int(ally)
        return Action(kind="heal", target_id=tid)

    def move_toward(self, pos_or_unit):
        if hasattr(pos_or_unit, "pos"):
            pos = pos_or_unit.pos
        else:
            pos = tuple(pos_or_unit)
        return Action(kind="move", target_pos=pos)


class WorldView:
    """Per-unit world view. Sensors are local — only what `me` can see."""

    def __init__(self, me_unit, world):
        self._me = me_unit
        self._world = world

    @property
    def tick(self):
        return self._world.tick

    @property
    def width(self):
        return self._world.width

    @property
    def height(self):
        return self._world.height

    @property
    def center(self):
        return self._world.map.center

    @property
    def my_spawn(self):
        if self._me.team == Team.RED:
            return self._world.map.red_spawn
        return self._world.map.blue_spawn

    @property
    def enemy_spawn(self):
        if self._me.team == Team.RED:
            return self._world.map.blue_spawn
        return self._world.map.red_spawn

    @property
    def obstacles(self):
        return tuple(self._world.obstacles)

    def _visible(self, predicate):
        result = []
        vision = self._me.spec.vision
        me_pos = self._me.pos
        obstacles = self._world.obstacles
        for u in self._world.units.values():
            if not u.alive or u.id == self._me.id:
                continue
            if not predicate(u):
                continue
            d = max(abs(me_pos[0] - u.pos[0]), abs(me_pos[1] - u.pos[1]))
            if d > vision:
                continue
            if not pathfinding.line_of_sight(me_pos, u.pos, obstacles):
                continue
            result.append(UnitView(u, self._world))
        return result

    def visible_enemies(self):
        return self._visible(lambda u: u.team != self._me.team)

    def visible_allies(self):
        return self._visible(lambda u: u.team == self._me.team)

    def line_of_sight(self, a_pos, b_pos):
        return pathfinding.line_of_sight(
            tuple(a_pos), tuple(b_pos), self._world.obstacles
        )

    def path(self, dest):
        if hasattr(dest, "pos"):
            dest = dest.pos
        else:
            dest = tuple(dest)
        occupied = self._world.occupied_cells() - {self._me.pos}
        return pathfinding.a_star(
            self._me.pos, dest,
            self._world.width, self._world.height,
            self._world.obstacles, occupied,
        )

    def recent_messages(self, last_ticks=10):
        cur = self._world.tick
        out = []
        for m in self._world.messages:
            if m.team != self._me.team:
                continue
            if m.unit_id == self._me.id:
                continue
            if cur - m.tick > last_ticks:
                continue
            out.append({
                "tick": m.tick,
                "from_id": m.unit_id,
                "from_pos": m.pos,
                "text": m.text,
            })
        return out

    def nearest_visible_enemy(self):
        enemies = self.visible_enemies()
        if not enemies:
            return None
        me_pos = self._me.pos
        return min(
            enemies,
            key=lambda e: (max(abs(e.pos[0] - me_pos[0]), abs(e.pos[1] - me_pos[1])), e.id),
        )
