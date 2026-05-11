from dataclasses import dataclass, field
from random import Random

from .types import Team, Unit, UnitType
from .unit_specs import UNIT_SPECS


DEFAULT_MAP_W = 64
DEFAULT_MAP_H = 36


@dataclass(frozen=True)
class Map:
    width: int
    height: int
    obstacles: frozenset
    red_spawn: tuple
    blue_spawn: tuple
    center: tuple


def default_map():
    w, h = DEFAULT_MAP_W, DEFAULT_MAP_H
    obs = set()
    # Symmetric cover: two rectangles on each side + a central wall pair.
    # Left side cover (red's right flank as it advances)
    for y in range(10, 16):
        obs.add((22, y))
    for y in range(20, 26):
        obs.add((22, y))
    # Right side cover (mirrors x=22 around x=31.5 in a width-64 map → 41)
    for y in range(10, 16):
        obs.add((41, y))
    for y in range(20, 26):
        obs.add((41, y))
    # Central wall pair
    for y in range(16, 20):
        obs.add((31, y))
        obs.add((32, y))
    return Map(
        width=w,
        height=h,
        obstacles=frozenset(obs),
        red_spawn=(5, h // 2),
        blue_spawn=(w - 6, h // 2),
        center=(w // 2, h // 2),
    )


@dataclass
class Message:
    tick: int
    unit_id: int
    team: Team
    pos: tuple
    text: str


@dataclass
class World:
    map: Map
    rng: Random
    tick: int = 0
    units: dict = field(default_factory=dict)
    messages: list = field(default_factory=list)
    event_log: list = field(default_factory=list)
    frame_events: list = field(default_factory=list)
    _next_id: int = 1

    @property
    def width(self):
        return self.map.width

    @property
    def height(self):
        return self.map.height

    @property
    def obstacles(self):
        return self.map.obstacles

    def occupied_cells(self):
        return {u.pos for u in self.units.values() if u.alive}

    def spawn_unit(self, utype: UnitType, team: Team, pos: tuple) -> Unit:
        spec = UNIT_SPECS[utype]
        u = Unit(
            id=self._next_id,
            type=utype,
            team=team,
            pos=pos,
            hp=spec.max_hp,
            spec=spec,
            spawn_tick=self.tick,
        )
        self._next_id += 1
        self.units[u.id] = u
        return u

    def alive_units(self, team=None):
        for u in self.units.values():
            if not u.alive:
                continue
            if team is not None and u.team != team:
                continue
            yield u

    def count_alive(self, team):
        return sum(1 for _ in self.alive_units(team))

    def surviving_value(self, team):
        return sum(u.spec.cost for u in self.alive_units(team))
