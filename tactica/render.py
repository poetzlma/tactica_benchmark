"""Minimal ASCII renderer for debugging headless runs."""


GLYPHS = {
    ("mbt", "red"): "T", ("mbt", "blue"): "t",
    ("infantry", "red"): "I", ("infantry", "blue"): "i",
    ("mortar", "red"): "M", ("mortar", "blue"): "m",
    ("medic", "red"): "H", ("medic", "blue"): "h",
    ("drone", "red"): "D", ("drone", "blue"): "d",
}


def render_ascii(world):
    grid = [["." for _ in range(world.width)] for _ in range(world.height)]
    for (ox, oy) in world.obstacles:
        grid[oy][ox] = "#"
    for u in world.units.values():
        if not u.alive:
            continue
        glyph = GLYPHS.get((u.type.value, u.team.value), "?")
        x, y = u.pos
        grid[y][x] = glyph
    return "\n".join("".join(row) for row in grid)
