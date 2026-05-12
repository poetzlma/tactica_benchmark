from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Team(Enum):
    RED = "red"
    BLUE = "blue"


class UnitType(Enum):
    MBT = "mbt"
    INFANTRY = "infantry"
    MORTAR = "mortar"
    MEDIC = "medic"
    DRONE = "drone"


@dataclass(frozen=True)
class UnitSpec:
    cost: int
    max_hp: int
    damage: int
    range: int
    move_period: int
    attack_cooldown: int
    vision: int
    can_heal: bool = False
    heal_amount: int = 0
    heal_cooldown: int = 0
    splash_radius: int = 0  # 0 = single-target. >0 = full damage to other enemies in radius, half to friendlies.

    def heal_cool(self) -> int:
        """Return the cooldown ticks for healing: heal_cooldown if set (>0), else attack_cooldown."""
        return self.heal_cooldown if self.heal_cooldown > 0 else self.attack_cooldown


@dataclass
class Action:
    kind: str  # 'hold' | 'move' | 'attack' | 'heal'
    target_pos: Optional[tuple] = None
    target_id: Optional[int] = None


@dataclass
class Unit:
    id: int
    type: UnitType
    team: Team
    pos: tuple
    hp: int
    spec: UnitSpec
    cooldown: int = 0
    move_cd: int = 0
    crashes: int = 0
    timeouts: int = 0
    alive: bool = True
    tactic: object = None
    kills_made: int = 0
    dmg_dealt: int = 0
    dmg_taken: int = 0
    idle_ticks: int = 0
    spawn_tick: int = 0
    death_tick: Optional[int] = None
