import heapq


def chebyshev(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def neighbors8(pos, w, h, obstacles):
    x, y = pos
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in obstacles:
                yield (nx, ny)


def a_star(start, goal, w, h, obstacles, blocked=None, max_expansions=4000):
    if blocked is None:
        blocked = set()
    if start == goal:
        return [start]
    if goal in obstacles:
        return None
    open_set = [(chebyshev(start, goal), 0, start)]
    came_from = {}
    g = {start: 0}
    closed = set()
    expansions = 0
    while open_set and expansions < max_expansions:
        _, g_cur, cur = heapq.heappop(open_set)
        if cur in closed:
            continue
        if cur == goal:
            path = [cur]
            while cur in came_from:
                cur = came_from[cur]
                path.append(cur)
            path.reverse()
            return path
        closed.add(cur)
        expansions += 1
        for n in neighbors8(cur, w, h, obstacles):
            if n in blocked and n != goal:
                continue
            cost = g_cur + 1
            if cost < g.get(n, 10**9):
                g[n] = cost
                came_from[n] = cur
                f = cost + chebyshev(n, goal)
                heapq.heappush(open_set, (f, cost, n))
    return None


def bresenham(a, b):
    x0, y0 = a
    x1, y1 = b
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    x, y = x0, y0
    while True:
        yield (x, y)
        if x == x1 and y == y1:
            return
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x += sx
        if e2 < dx:
            err += dx
            y += sy


def line_of_sight(a, b, obstacles):
    for cell in bresenham(a, b):
        if cell == a or cell == b:
            continue
        if cell in obstacles:
            return False
    return True
