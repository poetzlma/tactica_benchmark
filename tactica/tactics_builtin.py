"""Hardcoded tactic source strings used in the prototype.

These get loaded through the sandbox just like LLM-generated code would,
so we exercise the same path end-to-end.
"""


AGGRESSIVE_RUSH = """
class Tactic:
    def __init__(self):
        self.last_seen = None

    def tick(self, me, world):
        enemies = world.visible_enemies()
        if enemies:
            target = min(enemies, key=lambda e: (me.distance_to(e), e.id))
            self.last_seen = target.pos
            if me.can_attack(target):
                return me.attack(target)
            return me.move_toward(target.pos)
        if self.last_seen is not None:
            if me.pos == self.last_seen:
                self.last_seen = None
            else:
                return me.move_toward(self.last_seen)
        return me.move_toward(world.enemy_spawn)
"""


DEFENSIVE_TURTLE = """
class Tactic:
    def __init__(self):
        self.hold_pos = None

    def tick(self, me, world):
        if self.hold_pos is None:
            sx, sy = world.my_spawn
            ex, _ey = world.enemy_spawn
            dx = 1 if ex > sx else -1
            self.hold_pos = (sx + dx * 6, sy)
        enemies = world.visible_enemies()
        if enemies:
            in_range = [e for e in enemies if me.can_attack(e)]
            if in_range:
                target = min(in_range, key=lambda e: (e.hp, e.id))
                return me.attack(target)
            target = min(enemies, key=lambda e: (me.distance_to(e), e.id))
            if me.distance_to(target) > me.range:
                if me.distance_to(target) > me.range + 2:
                    return me.move_toward(target.pos)
                return me.hold()
            return me.hold()
        if me.pos != self.hold_pos:
            return me.move_toward(self.hold_pos)
        return me.hold()
"""


MEDIC_TACTIC = """
class Tactic:
    def __init__(self):
        pass

    def tick(self, me, world):
        allies = world.visible_allies()
        heal_now = [a for a in allies if a.hp < a.max_hp and me.can_heal(a)]
        if heal_now:
            target = min(heal_now, key=lambda a: (a.hp, a.id))
            return me.heal(target)
        wounded = [a for a in allies if a.hp < a.max_hp]
        if wounded:
            target = min(wounded, key=lambda a: (a.hp, a.id))
            return me.move_toward(target.pos)
        enemies = world.visible_enemies()
        if enemies:
            return me.move_toward(world.my_spawn)
        if allies:
            target = min(allies, key=lambda a: (me.distance_to(a), a.id))
            if me.distance_to(target) > 2:
                return me.move_toward(target.pos)
        return me.hold()
"""


DRONE_SCOUT = """
class Tactic:
    def __init__(self):
        self.target_dx = None

    def tick(self, me, world):
        enemies = world.visible_enemies()
        if enemies:
            nearest = min(enemies, key=lambda e: (me.distance_to(e), e.id))
            me.broadcast('enemy@' + str(nearest.pos[0]) + ',' + str(nearest.pos[1]))
            if me.hp < me.max_hp * 0.4:
                return me.move_toward(world.my_spawn)
            if me.can_attack(nearest) and me.distance_to(nearest) >= 2:
                return me.attack(nearest)
            if me.distance_to(nearest) < 2:
                sx, sy = world.my_spawn
                return me.move_toward((sx, me.pos[1]))
            return me.attack(nearest) if me.can_attack(nearest) else me.move_toward(nearest.pos)
        msgs = world.recent_messages(8)
        if msgs:
            latest = msgs[-1]
            return me.move_toward(latest['from_pos'])
        return me.move_toward(world.enemy_spawn)
"""
