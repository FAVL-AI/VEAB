"""Deterministic reference planners: no remote or physical actuation."""
from __future__ import annotations
import heapq
import math
from .spec import Scenario

CELL = 0.35


def clamp_vector(vx: float, vy: float, max_speed: float) -> tuple[float, float]:
    length = math.hypot(vx, vy)
    if length <= max_speed:
        return vx, vy
    return vx * max_speed / length, vy * max_speed / length


def traversable(s: Scenario, x: float, y: float, clearance: float = 0.08) -> bool:
    r = s.robot_radius + clearance
    if not (r <= x <= s.width - r and r <= y <= s.height - r):
        return False
    for o in s.obstacles:
        if (x - o.x) ** 2 + (y - o.y) ** 2 <= (o.radius + r) ** 2:
            return False
    for z in s.forbidden_zones:
        if z.x1 - r <= x <= z.x2 + r and z.y1 - r <= y <= z.y2 + r:
            return False
    return True


def route_cells(s: Scenario, start: tuple[float, float], goal: tuple[float, float]):
    """8-connected bounded A*, no diagonal corner cutting; no omniscient dynamic obstacles."""
    cols, rows = math.ceil(s.width / CELL), math.ceil(s.height / CELL)
    def point(cell):
        return (round((cell[0] + 0.5) * CELL, 5), round((cell[1] + 0.5) * CELL, 5))
    def cell(pos):
        return (min(cols-1, max(0, int(pos[0] / CELL))), min(rows-1, max(0, int(pos[1] / CELL))))
    start_cell, end_cell = cell(start), cell(goal)
    def free(c):
        return 0 <= c[0] < cols and 0 <= c[1] < rows and traversable(s, *point(c))
    if not free(start_cell):
        # Robot may be within an admissible margin but outside the gridded free set.
        options = [(math.dist(start, point((i, j))), (i, j))
                   for i in range(max(0, start_cell[0]-2), min(cols, start_cell[0]+3))
                   for j in range(max(0, start_cell[1]-2), min(rows, start_cell[1]+3)) if free((i, j))]
        if not options:
            return []
        start_cell = min(options)[1]
    if not free(end_cell):
        options = [(math.dist(goal, point((i, j))), (i, j))
                   for i in range(max(0, end_cell[0]-3), min(cols, end_cell[0]+4))
                   for j in range(max(0, end_cell[1]-3), min(rows, end_cell[1]+4)) if free((i, j))]
        if not options:
            return []
        end_cell = min(options)[1]
    queue = [(0.0, start_cell)]
    dist = {start_cell: 0.0}
    parent = {}
    counter = 0
    while queue and counter < 16000:
        counter += 1
        _, current = heapq.heappop(queue)
        if current == end_cell:
            route = [point(current)]
            while current in parent:
                current = parent[current]
                route.append(point(current))
            route.reverse()
            return route
        for dx, dy in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)):
            neighbor = current[0]+dx, current[1]+dy
            if not free(neighbor):
                continue
            if dx and dy and (not free((current[0]+dx, current[1])) or not free((current[0], current[1]+dy))):
                continue
            candidate = dist[current] + math.hypot(dx, dy)
            if candidate < dist.get(neighbor, math.inf):
                dist[neighbor] = candidate
                parent[neighbor] = current
                heuristic = math.dist(neighbor, end_cell)
                heapq.heappush(queue, (candidate + heuristic, neighbor))
    return []


class BaselineAgent:
    def __init__(self, policy: str, scenario: Scenario):
        if policy not in {"greedy", "route"}:
            raise ValueError("Unknown policy; allowed: greedy, route")
        self.policy = policy
        self.scenario = scenario
        self.path: list[tuple[float, float]] = []
        self.stage = -1
        self.replans = 0

    def act(self, visible_pos: tuple[float, float], stage: int, observed_present: bool | None):
        if observed_present is False:
            return (0.0, 0.0), {"decision": "abstain"}
        if stage >= len(self.scenario.waypoints):
            return (0.0, 0.0), {"decision": "stop"}
        goal = self.scenario.waypoints[stage]
        target = (goal.x, goal.y)
        if self.policy == "route":
            if self.stage != stage:
                self.path.clear()
                self.stage = stage
            if not self.path:
                self.path = route_cells(self.scenario, visible_pos, target)
                self.replans += 1
            while self.path and math.dist(visible_pos, self.path[0]) <= 0.22:
                self.path.pop(0)
            if not self.path:
                self.path = route_cells(self.scenario, visible_pos, target)
                self.replans += 1
            if self.path:
                target = self.path[0]
        dx, dy = target[0] - visible_pos[0], target[1] - visible_pos[1]
        mag = math.hypot(dx, dy)
        if mag < 0.015:
            return (0.0, 0.0), {"decision": "hold"}
        # Do not overshoot short cells during fixed time-step integration.
        speed = min(self.scenario.max_speed, mag / self.scenario.dt)
        return (round(speed * dx / mag, 6), round(speed * dy / mag, 6)), {"decision": "navigate", "replans": self.replans}
