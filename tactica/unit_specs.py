from .types import UnitSpec, UnitType


UNIT_SPECS = {
    UnitType.MBT: UnitSpec(
        cost=5, max_hp=350, damage=15, range=1,
        move_period=4, attack_cooldown=4, vision=6,
        splash_radius=1,
    ),
    UnitType.INFANTRY: UnitSpec(
        cost=3, max_hp=80, damage=25, range=1,
        move_period=2, attack_cooldown=3, vision=8,
    ),
    UnitType.MORTAR: UnitSpec(
        cost=4, max_hp=50, damage=20, range=8,
        move_period=2, attack_cooldown=6, vision=10,
    ),
    UnitType.MEDIC: UnitSpec(
        cost=4, max_hp=60, damage=0, range=4,
        move_period=2, attack_cooldown=2, vision=8,
        can_heal=True, heal_amount=15,
    ),
    UnitType.DRONE: UnitSpec(
        cost=2, max_hp=40, damage=8, range=2,
        move_period=1, attack_cooldown=3, vision=18,
    ),
}
