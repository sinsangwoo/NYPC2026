#!/usr/bin/env python3
"""
Standalone test to verify distance calculations
"""
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import NamedTuple


class Side(Enum):
    LEFT = "A"
    RIGHT = "B"


class BType(Enum):
    HQ = "HQ"
    BASE = "BASE"


class WState(Enum):
    STATIONARY = 0
    MOVING = 1


@dataclass(frozen=True)
class WarriorId:
    side: Side
    num: int


@dataclass
class Warrior:
    id: WarriorId
    region: int
    hp: int
    state: WState = WState.STATIONARY
    target: int = 0


@dataclass
class Building:
    region: int
    side: Side
    type: BType
    level: int = 1
    hp: int = 10


@dataclass
class GameMap:
    N: int = 0
    K: int = 0
    x: list[int] = field(default_factory=list)
    y: list[int] = field(default_factory=list)
    strongholds: list[int] = field(default_factory=list)
    adj: list[list[int]] = field(default_factory=list)
    my_side: Side = Side.LEFT
    my_hq: int = 0
    opp_hq: int = 0

    def hq_of(self, s: Side) -> int:
        return 0 if s is Side.LEFT else self.N - 1


@dataclass
class GameState:
    gold: int = 0
    my_countdown: int = 5
    opp_countdown: int = 5
    warriors: list[Warrior] = field(default_factory=list)
    buildings: list[Building] = field(default_factory=list)


@dataclass
class Paths:
    dist: list[list[float]]
    nxt: list[list[int]]


def euclid_ceil(M: GameMap, u: int, v: int) -> float:
    return math.ceil(math.hypot(M.x[u] - M.x[v], M.y[u] - M.y[v]))


def calculate_paths(M: GameMap) -> Paths:
    INF = math.inf
    N = M.N
    dist = [[INF] * N for _ in range(N)]
    nxt = [[-1] * N for _ in range(N)]

    for i in range(N):
        dist[i][i] = 0.0
        nxt[i][i] = i
    for u in range(N):
        for v in M.adj[u]:
            w = euclid_ceil(M, u, v)
            if w < dist[u][v]:
                dist[u][v] = w

    # Floyd-Warshall
    for k in range(N):
        dk = dist[k]
        for u in range(N):
            du = dist[u]
            duk = du[k]
            if duk == INF:
                continue
            for v in range(N):
                cand = duk + dk[v]
                if cand < du[v]:
                    du[v] = cand

    return Paths(dist, nxt)


def main():
    print("=== NYPC 2026 Distance Audit ===")
    
    # Load initialization data from forensic log
    M = GameMap()
    M.N = 81
    M.K = 13
    M.x = [-9784, -9926, -7078, -7558, -6132, -7708, -7217, -6456, -5991, -5103, -6968, -4442, -4668, -5733, -4496, -3769, -4215, -4899, -3835, -2551, -2648, -3142, -2274, -2282, -2473, -2514, -2480, -1883, -1935, -1677, -898, -1267, -574, -1503, -944, -633, -1352, -166, -39, -206, 0, 206, 39, 166, 1352, 633, 944, 1503, 574, 1267, 898, 1677, 1935, 1883, 2480, 2514, 2473, 2282, 2274, 3142, 2648, 2551, 3835, 4899, 4215, 3769, 4496, 5733, 4668, 4442, 6968, 5103, 5991, 6456, 7217, 7708, 6132, 7558, 7078, 9926, 9784]
    M.y = [4153, -16, 2957, 110, 1114, 6112, -1733, 7355, 4465, 3669, -4295, 5514, 190, -7984, -2160, -4909, 2966, 9535, 1537, -1527, 1341, 6381, 293, 10103, 2481, 7687, -9634, 3529, 4860, 6389, 6504, 8046, 2177, -6323, -8222, 7453, -3784, 10055, -6813, 4445, 0, -4445, 6813, -10055, 3784, -7453, 8222, 6323, -2177, -8046, -6504, -6389, -4860, -3529, 9634, -7687, -2481, -10103, -293, -6381, -1341, 1527, -1537, -9535, -2966, 4909, 2160, 7984, -190, -5514, 4295, -3669, -4465, -7355, 1733, -6112, -1114, -110, -2957, 16, -4153]
    M.strongholds = [2, 13, 14, 17, 20, 35, 40, 45, 60, 63, 66, 67, 78]
    M.adj = [
        [1, 2, 5],
        [0, 2, 3, 6, 10],
        [0, 1, 3, 4, 5, 8, 9],
        [1, 2, 4, 6, 12],
        [2, 3, 9, 12, 16, 18],
        [0, 2, 7, 8],
        [1, 3, 10, 12, 14],
        [5, 8, 11, 17, 21],
        [2, 5, 7, 9, 11],
        [2, 4, 8, 11, 16],
        [1, 6, 13, 14, 15],
        [7, 8, 9, 16, 21, 28],
        [3, 4, 6, 14, 18, 19, 22],
        [10, 15, 26, 33],
        [6, 10, 12, 15, 19, 36],
        [10, 13, 14, 33, 36],
        [4, 9, 11, 18, 24, 27, 28],
        [7, 21, 23, 25],
        [4, 12, 16, 20, 22, 24],
        [12, 14, 22, 36, 40, 48],
        [18, 22, 24, 32],
        [7, 11, 17, 25, 28, 29],
        [12, 18, 19, 20, 32, 40],
        [17, 25, 31, 37],
        [16, 18, 20, 27, 32],
        [17, 21, 23, 29, 31],
        [13, 33, 34, 43],
        [16, 24, 28, 32, 39],
        [11, 16, 21, 27, 29, 30, 39],
        [21, 25, 28, 30, 31, 35],
        [28, 29, 35, 39, 42],
        [23, 25, 29, 35, 37, 46],
        [20, 22, 24, 27, 39, 40, 44, 61],
        [13, 15, 26, 34, 36, 38, 41],
        [26, 33, 38, 43, 45, 49],
        [29, 30, 31, 42, 46],
        [14, 15, 19, 33, 41, 48],
        [23, 31, 46, 54],
        [33, 34, 41, 45, 50],
        [27, 28, 30, 32, 42, 44, 47],
        [19, 22, 32, 48, 58, 61],
        [33, 36, 38, 48, 50, 52, 53],
        [30, 35, 39, 46, 47],
        [26, 34, 49, 57],
        [32, 39, 47, 61, 65, 66],
        [34, 38, 49, 50, 51],
        [31, 35, 37, 42, 47, 54],
        [39, 42, 44, 46, 54, 65, 67],
        [19, 36, 40, 41, 53, 56, 58, 60],
        [34, 43, 45, 51, 55, 57],
        [38, 41, 45, 51, 52],
        [45, 49, 50, 52, 55, 59],
        [41, 50, 51, 53, 59, 64, 69],
        [41, 48, 52, 56, 64],
        [37, 46, 47, 67],
        [49, 51, 57, 59, 63],
        [48, 53, 60, 62, 64],
        [43, 49, 55, 63],
        [40, 48, 60, 61, 62, 68],
        [51, 52, 55, 63, 69, 73],
        [48, 56, 58, 62],
        [32, 40, 44, 58, 66, 68],
        [56, 58, 60, 64, 68, 76],
        [55, 57, 59, 73],
        [52, 53, 56, 62, 69, 71, 76],
        [44, 47, 66, 67, 70],
        [44, 61, 65, 68, 70, 74],
        [47, 54, 65, 70],
        [58, 61, 62, 66, 74, 76, 77],
        [52, 59, 64, 71, 72, 73],
        [65, 66, 67, 74, 79],
        [64, 69, 72, 76, 78],
        [69, 71, 73, 75, 78],
        [59, 63, 69, 72, 75],
        [66, 68, 70, 77, 79],
        [72, 73, 78, 80],
        [62, 64, 68, 71, 77, 78],
        [68, 74, 76, 78, 79],
        [71, 72, 75, 76, 77, 79, 80],
        [70, 74, 77, 78, 80],
        [75, 78, 79]
    ]
    
    # HQs
    M.my_side = Side.LEFT
    M.my_hq = 0
    M.opp_hq = 80
    
    print(f"GameMap initialized: N={M.N}, my_hq={M.my_hq}, opp_hq={M.opp_hq}")
    print(f"Region 0: x={M.x[0]}, y={M.y[0]}")
    print(f"Region 1: x={M.x[1]}, y={M.y[1]}")
    print(f"Region 80: x={M.x[80]}, y={M.y[80]}")
    
    # Euclid ceil examples
    print("\n=== Euclid Ceil Examples:")
    print(f"euclid_ceil(0, 80) = {euclid_ceil(M, 0, 80)}")
    print(f"euclid_ceil(0, 1) = {euclid_ceil(M, 0, 1)}")
    print(f"euclid_ceil(1, 80) = {euclid_ceil(M, 1, 80)}")
    
    # Calculate paths
    print("\n=== Calculating Floyd-Warshall Paths...")
    P = calculate_paths(M)
    
    print("\n=== Distance Matrix Results:")
    print(f"dist[0][80] = {P.dist[0][80]}")
    print(f"dist[1][80] = {P.dist[1][80]}")
    print(f"dist[2][80] = {P.dist[2][80]}")
    print(f"dist[5][80] = {P.dist[5][80]}")
    print(f"dist[0][1] = {P.dist[0][1]}")
    print(f"dist[0][2] = {P.dist[0][2]}")
    print(f"dist[0][5] = {P.dist[0][5]}")
    
    print("\n=== Distance Matrix Info:")
    print(f"Size: {len(P.dist)}x{len(P.dist[0])}")
    print(f"Data type: float")
    print(f"INF value: math.inf")
    
    # Find max distance
    max_dist = 0
    min_dist = float('inf')
    total_dist = 0
    count_dist = 0
    for u in range(M.N):
        for v in range(M.N):
            if P.dist[u][v] != float('inf'):
                max_dist = max(max_dist, P.dist[u][v])
                min_dist = min(min_dist, P.dist[u][v])
                total_dist += P.dist[u][v]
                count_dist += 1
    avg_dist = total_dist / count_dist if count_dist > 0 else 0
    
    print(f"Max distance: {max_dist}")
    print(f"Min distance: {min_dist}")
    print(f"Avg distance: {avg_dist:.2f}")
    
    print("\n=== Audit Complete ===")


if __name__ == "__main__":
    main()
