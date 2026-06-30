#!/usr/bin/env python3
"""
NYPC AI 전략 분석 플랫폼 - STEP 2
로그 분석, 패턴 추출, Feature Vector 생성
"""

import json
import csv
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Set
from collections import defaultdict, Counter


# =============================================================================
# Parser 모듈: 로그 → 이벤트
# =============================================================================

@dataclass
class MapData:
    N: int = 0
    K: int = 0
    x: List[int] = field(default_factory=list)
    y: List[int] = field(default_factory=list)
    strongholds: List[int] = field(default_factory=list)
    adj: List[List[int]] = field(default_factory=list)


@dataclass
class CommandEvent:
    turn: int
    side: str
    commands: List[str]


@dataclass
class TrainEvent:
    turn: int
    warrior_ids: List[str]


@dataclass
class MoveEvent:
    turn: int
    warrior_id: str
    region: int


@dataclass
class DamageEvent:
    turn: int
    cause: str
    warrior_id: str
    amount: int


@dataclass
class SiegeEvent:
    turn: int
    side: str
    region: int
    damage: int


@dataclass
class UpgradeEvent:
    turn: int
    side: str
    region: int


@dataclass
class TimeEvent:
    turn: int
    left_time: int
    left_tokens: int
    right_time: int
    right_tokens: int


@dataclass
class ResultEvent:
    winner: str
    reason: str


@dataclass
class MatchEvents:
    match_id: int
    left_command: str
    right_command: str
    map_data: MapData
    commands: Dict[int, Tuple[CommandEvent, CommandEvent]]
    times: Dict[int, TimeEvent]
    trains: Dict[int, TrainEvent]
    moves: Dict[int, List[MoveEvent]]
    damages: Dict[int, List[DamageEvent]]
    sieges: Dict[int, List[SiegeEvent]]
    upgrades: Dict[int, List[UpgradeEvent]]
    result: Optional[ResultEvent]


class LogParser:
    """로그 파일을 파싱하여 이벤트로 변환"""

    @staticmethod
    def parse_log(log_path: Path, match_id: int) -> MatchEvents:
        with open(log_path, 'r', encoding='utf-8') as f:
            lines = [line.rstrip('\n') for line in f]

        events = MatchEvents(
            match_id=match_id,
            left_command="",
            right_command="",
            map_data=MapData(),
            commands={},
            times={},
            trains={},
            moves={},
            damages={},
            sieges={},
            upgrades={},
            result=None
        )

        idx = 0
        n = len(lines)

        # 초기 명령 읽기
        if idx < n and lines[idx].startswith('[LEFT "COMMAND:'):
            events.left_command = lines[idx][len('[LEFT "COMMAND: '):-2]
            idx += 1
        if idx < n and lines[idx].startswith('[RIGHT "COMMAND:'):
            events.right_command = lines[idx][len('[RIGHT "COMMAND: '):-2]
            idx += 1

        # MAP 블록
        if idx < n and lines[idx] == "MAP":
            idx += 1
            events.map_data = LogParser._parse_map(lines, idx)
            while idx < n and lines[idx] != "END MAP":
                idx += 1
            idx += 1

        # 턴별 이벤트
        current_turn = None
        while idx < n:
            line = lines[idx]

            if line.startswith("TURN ") and not line.endswith("RESULT"):
                current_turn = int(line.split()[1])
                idx += 1

                # COMMAND 블록
                left_cmd = CommandEvent(turn=current_turn, side="LEFT", commands=[])
                right_cmd = CommandEvent(turn=current_turn, side="RIGHT", commands=[])

                if idx < n and lines[idx] == "COMMAND LEFT START":
                    idx += 1
                    while idx < n and lines[idx] != "COMMAND LEFT END":
                        left_cmd.commands.append(lines[idx])
                        idx += 1
                    idx += 1

                if idx < n and lines[idx] == "COMMAND RIGHT START":
                    idx += 1
                    while idx < n and lines[idx] != "COMMAND RIGHT END":
                        right_cmd.commands.append(lines[idx])
                        idx += 1
                    idx += 1

                events.commands[current_turn] = (left_cmd, right_cmd)

            elif line.startswith("TURN ") and line.endswith("RESULT"):
                current_turn = int(line.split()[1])
                idx += 1

                events.trains.setdefault(current_turn, TrainEvent(turn=current_turn, warrior_ids=[]))
                events.moves.setdefault(current_turn, [])
                events.damages.setdefault(current_turn, [])
                events.sieges.setdefault(current_turn, [])
                events.upgrades.setdefault(current_turn, [])

                while idx < n and not lines[idx].startswith("END TURN"):
                    line = lines[idx]

                    if line.startswith("TIME LEFT"):
                        parts = line.split()
                        events.times[current_turn] = TimeEvent(
                            turn=current_turn,
                            left_time=int(parts[2]),
                            left_tokens=int(parts[3]),
                            right_time=int(parts[5]),
                            right_tokens=int(parts[6])
                        )
                        idx += 1

                    elif line.startswith("UPGRADE"):
                        parts = line.split()
                        events.upgrades[current_turn].append(UpgradeEvent(
                            turn=current_turn,
                            side=parts[1],
                            region=int(parts[2])
                        ))
                        idx += 1

                    elif line.startswith("TRAIN"):
                        parts = line.split()
                        events.trains[current_turn] = TrainEvent(
                            turn=current_turn,
                            warrior_ids=parts[1:] if len(parts) > 1 else []
                        )
                        idx += 1

                    elif line.startswith("MOVE"):
                        parts = line.split()
                        events.moves[current_turn].append(MoveEvent(
                            turn=current_turn,
                            warrior_id=parts[1],
                            region=int(parts[2])
                        ))
                        idx += 1

                    elif line.startswith("DAMAGE"):
                        parts = line.split()
                        events.damages[current_turn].append(DamageEvent(
                            turn=current_turn,
                            cause=parts[1],
                            warrior_id=parts[2],
                            amount=int(parts[3])
                        ))
                        idx += 1

                    elif line.startswith("SIEGE"):
                        parts = line.split()
                        events.sieges[current_turn].append(SiegeEvent(
                            turn=current_turn,
                            side=parts[1],
                            region=int(parts[2]),
                            damage=int(parts[3])
                        ))
                        idx += 1

                    else:
                        idx += 1

                if idx < n and lines[idx].startswith("END TURN"):
                    idx += 1

            elif line.startswith("RESULT"):
                parts = line.split()
                events.result = ResultEvent(winner=parts[1], reason=parts[2])
                idx += 1

            else:
                idx += 1

        return events

    @staticmethod
    def _parse_map(lines: List[str], idx: int) -> MapData:
        map_data = MapData()

        # 첫 줄: N K
        parts = lines[idx].split()
        map_data.N = int(parts[0])
        map_data.K = int(parts[1])
        idx += 1

        # x 좌표
        map_data.x = list(map(int, lines[idx].split()))
        idx += 1

        # y 좌표
        map_data.y = list(map(int, lines[idx].split()))
        idx += 1

        # STRONGHOLDS
        if lines[idx].startswith("STRONGHOLDS"):
            map_data.strongholds = list(map(int, lines[idx].split()[1:]))
            idx += 1

        # 인접 리스트
        map_data.adj = []
        for _ in range(map_data.N):
            parts = lines[idx].split()
            adj = list(map(int, parts[1:])) if len(parts) > 1 else []
            map_data.adj.append(adj)
            idx += 1

        return map_data


# =============================================================================
# Event Tracker 모듈: 턴별 이벤트 정리
# =============================================================================

@dataclass
class WarriorTrack:
    warrior_id: str
    path: List[Tuple[int, int]]  # (turn, region)
    created_turn: Optional[int] = None
    last_seen_turn: Optional[int] = None


@dataclass
class TrackedEvents:
    match_id: int
    map_data: MapData
    turns: List[int]
    warriors: Dict[str, WarriorTrack]
    result: Optional[ResultEvent]


class EventTracker:
    """이벤트를 턴별로 추적하고 정리"""

    @staticmethod
    def track(events: MatchEvents) -> TrackedEvents:
        tracked = TrackedEvents(
            match_id=events.match_id,
            map_data=events.map_data,
            turns=sorted(events.commands.keys()),
            warriors={},
            result=events.result
        )

        # 초기 전사 (A1-A3, B1-B3)
        for side in ["A", "B"]:
            for num in [1, 2, 3]:
                wid = f"{side}{num}"
                tracked.warriors[wid] = WarriorTrack(
                    warrior_id=wid,
                    path=[],
                    created_turn=0
                )

        # 턴별 이벤트 추적
        for turn in tracked.turns:
            # TRAIN
            if turn in events.trains and events.trains[turn].warrior_ids:
                for wid in events.trains[turn].warrior_ids:
                    if wid not in tracked.warriors:
                        tracked.warriors[wid] = WarriorTrack(
                            warrior_id=wid,
                            path=[],
                            created_turn=turn
                        )

            # MOVE
            if turn in events.moves:
                for move in events.moves[turn]:
                    wid = move.warrior_id
                    if wid in tracked.warriors:
                        tracked.warriors[wid].path.append((turn, move.region))
                        tracked.warriors[wid].last_seen_turn = turn

        return tracked


# =============================================================================
# Metric Extractor 모듈: 순수 수치 추출
# =============================================================================

@dataclass
class Metrics:
    # 경기 기본 정보
    match_id: int
    winner: str
    reason: str
    total_turns: int

    # TRAIN 관련
    first_train_turn: Optional[int]
    train_count: int
    trained_units: List[str]

    # DAMAGE 관련
    first_damage_turn: Optional[int]
    first_combat_turn: Optional[int]
    first_turret_turn: Optional[int]
    first_hunger_turn: Optional[int]
    total_damage_combat: int
    total_damage_turret: int
    total_damage_hunger: int

    # SIEGE 관련
    first_siege_turn: Optional[int]
    total_siege_damage: int
    siege_count: int
    sieged_regions: Set[int]

    # 시간 관련
    avg_time_left: float
    avg_time_right: float
    max_time_left: int
    max_time_right: int

    # 이동 관련
    total_moves: int
    avg_moves_per_turn: float


class MetricExtractor:
    """이벤트에서 수치 메트릭 추출"""

    @staticmethod
    def extract(events: MatchEvents) -> Metrics:
        turns = sorted(events.commands.keys())
        total_turns = max(turns) if turns else 0

        # TRAIN 메트릭
        first_train_turn = None
        train_count = 0
        trained_units = []
        for turn in sorted(events.trains.keys()):
            train = events.trains[turn]
            if train.warrior_ids:
                if first_train_turn is None:
                    first_train_turn = turn
                train_count += len(train.warrior_ids)
                trained_units.extend(train.warrior_ids)

        # DAMAGE 메트릭
        first_damage_turn = None
        first_combat_turn = None
        first_turret_turn = None
        first_hunger_turn = None
        total_damage_combat = 0
        total_damage_turret = 0
        total_damage_hunger = 0

        for turn in sorted(events.damages.keys()):
            for dmg in events.damages[turn]:
                if first_damage_turn is None:
                    first_damage_turn = turn

                if dmg.cause == "COMBAT":
                    total_damage_combat += dmg.amount
                    if first_combat_turn is None:
                        first_combat_turn = turn
                elif dmg.cause == "TURRET":
                    total_damage_turret += dmg.amount
                    if first_turret_turn is None:
                        first_turret_turn = turn
                elif dmg.cause == "HUNGER":
                    total_damage_hunger += dmg.amount
                    if first_hunger_turn is None:
                        first_hunger_turn = turn

        # SIEGE 메트릭
        first_siege_turn = None
        total_siege_damage = 0
        siege_count = 0
        sieged_regions = set()

        for turn in sorted(events.sieges.keys()):
            for siege in events.sieges[turn]:
                if first_siege_turn is None:
                    first_siege_turn = turn
                total_siege_damage += siege.damage
                siege_count += 1
                sieged_regions.add(siege.region)

        # 시간 메트릭
        times = list(events.times.values())
        avg_time_left = sum(t.left_time for t in times) / len(times) if times else 0
        avg_time_right = sum(t.right_time for t in times) / len(times) if times else 0
        max_time_left = max(t.left_time for t in times) if times else 0
        max_time_right = max(t.right_time for t in times) if times else 0

        # 이동 메트릭
        total_moves = sum(len(moves) for moves in events.moves.values())
        avg_moves_per_turn = total_moves / total_turns if total_turns > 0 else 0

        winner = events.result.winner if events.result else "UNKNOWN"
        reason = events.result.reason if events.result else "UNKNOWN"

        return Metrics(
            match_id=events.match_id,
            winner=winner,
            reason=reason,
            total_turns=total_turns,
            first_train_turn=first_train_turn,
            train_count=train_count,
            trained_units=trained_units,
            first_damage_turn=first_damage_turn,
            first_combat_turn=first_combat_turn,
            first_turret_turn=first_turret_turn,
            first_hunger_turn=first_hunger_turn,
            total_damage_combat=total_damage_combat,
            total_damage_turret=total_damage_turret,
            total_damage_hunger=total_damage_hunger,
            first_siege_turn=first_siege_turn,
            total_siege_damage=total_siege_damage,
            siege_count=siege_count,
            sieged_regions=sieged_regions,
            avg_time_left=avg_time_left,
            avg_time_right=avg_time_right,
            max_time_left=max_time_left,
            max_time_right=max_time_right,
            total_moves=total_moves,
            avg_moves_per_turn=avg_moves_per_turn
        )


# =============================================================================
# Pattern Extractor 모듈: 행동 패턴 추출
# =============================================================================

@dataclass
class OpeningPattern:
    first_10_turns: List[Tuple[int, List[str], List[str]]]  # (turn, left_cmds, right_cmds)
    first_move_turn: Optional[int]
    first_train_turn: Optional[int]
    first_combat_turn: Optional[int]


@dataclass
class MovementPattern:
    node_visits: Counter[int]
    edge_traffic: Counter[Tuple[int, int]]
    warrior_paths: Dict[str, List[int]]


@dataclass
class CombatPattern:
    damage_by_turn: Dict[int, Dict[str, int]]
    combat_turns: Set[int]


@dataclass
class SiegePattern:
    siege_by_turn: Dict[int, int]
    sieged_nodes: Set[int]


@dataclass
class Patterns:
    opening: OpeningPattern
    movement: MovementPattern
    combat: CombatPattern
    siege: SiegePattern


class PatternExtractor:
    """이벤트에서 행동 패턴 추출"""

    @staticmethod
    def extract(events: MatchEvents, tracked: TrackedEvents, metrics: Metrics) -> Patterns:
        # Opening 패턴
        first_10 = []
        for turn in range(1, 11):
            if turn in events.commands:
                left_cmd, right_cmd = events.commands[turn]
                first_10.append((turn, left_cmd.commands.copy(), right_cmd.commands.copy()))
            else:
                first_10.append((turn, [], []))

        opening = OpeningPattern(
            first_10_turns=first_10,
            first_move_turn=PatternExtractor._find_first_move(events),
            first_train_turn=metrics.first_train_turn,
            first_combat_turn=metrics.first_combat_turn
        )

        # Movement 패턴
        node_visits = Counter()
        edge_traffic = Counter()
        warrior_paths = {}

        for wid, track in tracked.warriors.items():
            path = []
            prev_region = None
            for turn, region in track.path:
                node_visits[region] += 1
                if prev_region is not None and prev_region != region:
                    edge_traffic[(prev_region, region)] += 1
                path.append(region)
                prev_region = region
            warrior_paths[wid] = path

        movement = MovementPattern(
            node_visits=node_visits,
            edge_traffic=edge_traffic,
            warrior_paths=warrior_paths
        )

        # Combat 패턴
        damage_by_turn = defaultdict(lambda: {"COMBAT": 0, "TURRET": 0, "HUNGER": 0})
        combat_turns = set()

        for turn in events.damages:
            for dmg in events.damages[turn]:
                damage_by_turn[turn][dmg.cause] += dmg.amount
                if dmg.cause == "COMBAT":
                    combat_turns.add(turn)

        combat = CombatPattern(
            damage_by_turn=dict(damage_by_turn),
            combat_turns=combat_turns
        )

        # Siege 패턴
        siege_by_turn = defaultdict(int)
        sieged_nodes = set()

        for turn in events.sieges:
            for siege in events.sieges[turn]:
                siege_by_turn[turn] += siege.damage
                sieged_nodes.add(siege.region)

        siege = SiegePattern(
            siege_by_turn=dict(siege_by_turn),
            sieged_nodes=sieged_nodes
        )

        return Patterns(
            opening=opening,
            movement=movement,
            combat=combat,
            siege=siege
        )

    @staticmethod
    def _find_first_move(events: MatchEvents) -> Optional[int]:
        for turn in sorted(events.moves.keys()):
            if events.moves[turn]:
                return turn
        return None


# =============================================================================
# Feature Extractor 모듈: Feature Vector 생성
# =============================================================================

@dataclass
class Features:
    # 경기 기본
    match_id: int
    winner: int  # -1=DRAW, 0=LEFT, 1=RIGHT
    reason: str
    total_turns: int

    # Opening (1~10턴)
    opening_turn_1: str
    opening_turn_2: str
    opening_turn_3: str
    opening_turn_4: str
    opening_turn_5: str
    opening_turn_6: str
    opening_turn_7: str
    opening_turn_8: str
    opening_turn_9: str
    opening_turn_10: str

    # TRAIN
    first_train_turn: float
    train_count: int

    # DAMAGE
    first_damage_turn: float
    first_combat_turn: float
    first_turret_turn: float
    first_hunger_turn: float
    total_damage_combat: int
    total_damage_turret: int
    total_damage_hunger: int

    # SIEGE
    first_siege_turn: float
    total_siege_damage: int
    siege_count: int

    # 시간
    avg_time_left: float
    avg_time_right: float

    # 이동
    total_moves: int
    avg_moves_per_turn: float

    # 게임 메커니즘과 직결된 특성
    hunger_index: int
    turret_risk: float
    siege_efficiency: float
    training_efficiency: float


class FeatureExtractor:
    """메트릭과 패턴에서 Feature Vector 생성 (STEP3에서 직접 사용 가능)"""

    @staticmethod
    def extract(metrics: Metrics, patterns: Patterns) -> Features:
        # Winner 인코딩
        winner = -1
        if metrics.winner == "LEFT_WIN":
            winner = 0
        elif metrics.winner == "RIGHT_WIN":
            winner = 1

        # Opening 인코딩
        def encode_turn(turn_cmds: List[str]) -> str:
            if not turn_cmds:
                return "NONE"
            has_train = any(cmd.startswith("TRAIN") for cmd in turn_cmds)
            has_upgrade = any(cmd.startswith("UPGRADE") for cmd in turn_cmds)
            has_move = any(cmd.startswith("MOVE") for cmd in turn_cmds)
            parts = []
            if has_move:
                parts.append("MOVE")
            if has_train:
                parts.append("TRAIN")
            if has_upgrade:
                parts.append("UPGRADE")
            return "_".join(parts) if parts else "NONE"

        opening_turns = ["NONE"] * 10
        for turn_idx in range(10):
            if turn_idx < len(patterns.opening.first_10_turns):
                turn, left_cmds, right_cmds = patterns.opening.first_10_turns[turn_idx]
                opening_turns[turn_idx] = encode_turn(left_cmds + right_cmds)

        # 게임 메커니즘 특성
        # Hunger Index: HUNGER로 인한 총 데미지
        hunger_index = metrics.total_damage_hunger

        # Turret Risk: TURRET 데미지 / 전체 데미지
        total_damage = metrics.total_damage_combat + metrics.total_damage_turret + metrics.total_damage_hunger
        turret_risk = metrics.total_damage_turret / total_damage if total_damage > 0 else 0

        # Siege Efficiency: 총 공성 데미지 / 총 전투 데미지
        siege_efficiency = 0
        if metrics.total_damage_combat > 0:
            siege_efficiency = metrics.total_siege_damage / metrics.total_damage_combat

        # Training Efficiency: 첫 TRAIN ~ 첫 SIEGE까지의 턴 수
        training_efficiency = float('inf')
        if metrics.first_train_turn is not None and metrics.first_siege_turn is not None:
            training_efficiency = metrics.first_siege_turn - metrics.first_train_turn

        return Features(
            match_id=metrics.match_id,
            winner=winner,
            reason=metrics.reason,
            total_turns=metrics.total_turns,
            opening_turn_1=opening_turns[0],
            opening_turn_2=opening_turns[1],
            opening_turn_3=opening_turns[2],
            opening_turn_4=opening_turns[3],
            opening_turn_5=opening_turns[4],
            opening_turn_6=opening_turns[5],
            opening_turn_7=opening_turns[6],
            opening_turn_8=opening_turns[7],
            opening_turn_9=opening_turns[8],
            opening_turn_10=opening_turns[9],
            first_train_turn=metrics.first_train_turn if metrics.first_train_turn else float('inf'),
            train_count=metrics.train_count,
            first_damage_turn=metrics.first_damage_turn if metrics.first_damage_turn else float('inf'),
            first_combat_turn=metrics.first_combat_turn if metrics.first_combat_turn else float('inf'),
            first_turret_turn=metrics.first_turret_turn if metrics.first_turret_turn else float('inf'),
            first_hunger_turn=metrics.first_hunger_turn if metrics.first_hunger_turn else float('inf'),
            total_damage_combat=metrics.total_damage_combat,
            total_damage_turret=metrics.total_damage_turret,
            total_damage_hunger=metrics.total_damage_hunger,
            first_siege_turn=metrics.first_siege_turn if metrics.first_siege_turn else float('inf'),
            total_siege_damage=metrics.total_siege_damage,
            siege_count=metrics.siege_count,
            avg_time_left=metrics.avg_time_left,
            avg_time_right=metrics.avg_time_right,
            total_moves=metrics.total_moves,
            avg_moves_per_turn=metrics.avg_moves_per_turn,
            hunger_index=hunger_index,
            turret_risk=turret_risk,
            siege_efficiency=siege_efficiency,
            training_efficiency=training_efficiency
        )


# =============================================================================
# Map Analyzer 모듈: Transition Matrix 등 맵 분석
# =============================================================================

@dataclass
class MapAnalysis:
    transition_matrix: Dict[str, Dict[str, int]]
    node_visits: Dict[int, int]
    stronghold_visits: Dict[int, int]


class MapAnalyzer:
    """맵과 이동 패턴 분석"""

    @staticmethod
    def analyze(map_data: MapData, patterns: Patterns) -> MapAnalysis:
        # Transition Matrix
        transition_matrix = defaultdict(lambda: defaultdict(int))
        for (from_node, to_node), count in patterns.movement.edge_traffic.items():
            transition_matrix[str(from_node)][str(to_node)] = count

        # Node visits
        node_visits = dict(patterns.movement.node_visits)

        # Stronghold visits
        stronghold_visits = {}
        for stronghold in map_data.strongholds:
            stronghold_visits[stronghold] = node_visits.get(stronghold, 0)

        return MapAnalysis(
            transition_matrix=dict(transition_matrix),
            node_visits=node_visits,
            stronghold_visits=stronghold_visits
        )


# =============================================================================
# Exporter 모듈: 다양한 형식으로 출력
# =============================================================================

class Exporter:
    """분석 결과를 다양한 형식으로 내보내기"""

    def __init__(self, analysis_dir: Path):
        self.analysis_dir = analysis_dir
        self.analysis_dir.mkdir(parents=True, exist_ok=True)

    def export_match(self, match_id: int, events: MatchEvents, tracked: TrackedEvents,
                     metrics: Metrics, patterns: Patterns, features: Features,
                     map_analysis: MapAnalysis):
        """단일 경기 분석 결과 내보내기"""
        match_dir = self.analysis_dir / f"match_{match_id:04d}"
        match_dir.mkdir(exist_ok=True)

        # Timeline
        self._export_timeline(match_dir, events, tracked)

        # Metrics
        self._export_metrics(match_dir, metrics)

        # Patterns
        self._export_patterns(match_dir, patterns)

        # Opening Signature
        self._export_opening_signature(match_dir, patterns)

        # Map Analysis
        self._export_map_analysis(match_dir, map_analysis)

    def export_summary(self, all_features: List[Features]):
        """전체 경기 요약 (STEP3에서 직접 사용할 CSV)"""
        # Features CSV
        features_path = self.analysis_dir / "features.csv"
        self._export_features_csv(features_path, all_features)

    def _export_timeline(self, match_dir: Path, events: MatchEvents, tracked: TrackedEvents):
        timeline = {
            "match_id": tracked.match_id,
            "turns": []
        }

        for turn in sorted(events.commands.keys()):
            left_cmd, right_cmd = events.commands[turn]
            turn_data = {
                "turn": turn,
                "left_commands": left_cmd.commands,
                "right_commands": right_cmd.commands,
                "moves": [],
                "damages": [],
                "sieges": [],
                "upgrades": []
            }

            if turn in events.moves:
                for move in events.moves[turn]:
                    turn_data["moves"].append({
                        "warrior": move.warrior_id,
                        "region": move.region
                    })

            if turn in events.damages:
                for dmg in events.damages[turn]:
                    turn_data["damages"].append({
                        "cause": dmg.cause,
                        "warrior": dmg.warrior_id,
                        "amount": dmg.amount
                    })

            if turn in events.sieges:
                for siege in events.sieges[turn]:
                    turn_data["sieges"].append({
                        "side": siege.side,
                        "region": siege.region,
                        "damage": siege.damage
                    })

            if turn in events.upgrades:
                for upg in events.upgrades[turn]:
                    turn_data["upgrades"].append({
                        "side": upg.side,
                        "region": upg.region
                    })

            timeline["turns"].append(turn_data)

        with open(match_dir / "timeline.json", 'w', encoding='utf-8') as f:
            json.dump(timeline, f, indent=2)

    def _export_metrics(self, match_dir: Path, metrics: Metrics):
        metrics_dict = {
            "match_id": metrics.match_id,
            "winner": metrics.winner,
            "reason": metrics.reason,
            "total_turns": metrics.total_turns,
            "first_train_turn": metrics.first_train_turn,
            "train_count": metrics.train_count,
            "trained_units": metrics.trained_units,
            "first_combat_turn": metrics.first_combat_turn,
            "first_siege_turn": metrics.first_siege_turn,
            "total_damage_combat": metrics.total_damage_combat,
            "total_damage_turret": metrics.total_damage_turret,
            "total_damage_hunger": metrics.total_damage_hunger,
            "total_siege_damage": metrics.total_siege_damage,
            "siege_count": metrics.siege_count,
            "total_moves": metrics.total_moves
        }
        with open(match_dir / "metrics.json", 'w', encoding='utf-8') as f:
            json.dump(metrics_dict, f, indent=2)

    def _export_patterns(self, match_dir: Path, patterns: Patterns):
        patterns_dict = {
            "movement": {
                "node_visits": dict(patterns.movement.node_visits),
                "edge_traffic": {f"{u}_{v}": c for (u, v), c in patterns.movement.edge_traffic.items()},
                "warrior_paths": patterns.movement.warrior_paths
            },
            "combat": {
                "damage_by_turn": {str(k): v for k, v in patterns.combat.damage_by_turn.items()},
                "combat_turns": sorted(list(patterns.combat.combat_turns))
            },
            "siege": {
                "siege_by_turn": {str(k): v for k, v in patterns.siege.siege_by_turn.items()},
                "sieged_nodes": sorted(list(patterns.siege.sieged_nodes))
            }
        }
        with open(match_dir / "patterns.json", 'w', encoding='utf-8') as f:
            json.dump(patterns_dict, f, indent=2)

    def _export_opening_signature(self, match_dir: Path, patterns: Patterns):
        signature = {
            "turn_commands": [],
            "first_events": {
                "first_move_turn": patterns.opening.first_move_turn,
                "first_train_turn": patterns.opening.first_train_turn,
                "first_combat_turn": patterns.opening.first_combat_turn
            }
        }
        for turn, left_cmds, right_cmds in patterns.opening.first_10_turns:
            signature["turn_commands"].append({
                "turn": turn,
                "left": left_cmds,
                "right": right_cmds
            })
        with open(match_dir / "opening_signature.json", 'w', encoding='utf-8') as f:
            json.dump(signature, f, indent=2)

    def _export_map_analysis(self, match_dir: Path, map_analysis: MapAnalysis):
        map_analysis_dict = {
            "transition_matrix": map_analysis.transition_matrix,
            "node_visits": map_analysis.node_visits,
            "stronghold_visits": map_analysis.stronghold_visits
        }
        with open(match_dir / "map_analysis.json", 'w', encoding='utf-8') as f:
            json.dump(map_analysis_dict, f, indent=2)

    def _export_features_csv(self, features_path: Path, all_features: List[Features]):
        fieldnames = [
            "match_id", "winner", "reason", "total_turns",
            "opening_turn_1", "opening_turn_2", "opening_turn_3", "opening_turn_4", "opening_turn_5",
            "opening_turn_6", "opening_turn_7", "opening_turn_8", "opening_turn_9", "opening_turn_10",
            "first_train_turn", "train_count",
            "first_damage_turn", "first_combat_turn", "first_turret_turn", "first_hunger_turn",
            "total_damage_combat", "total_damage_turret", "total_damage_hunger",
            "first_siege_turn", "total_siege_damage", "siege_count",
            "avg_time_left", "avg_time_right",
            "total_moves", "avg_moves_per_turn",
            "hunger_index", "turret_risk", "siege_efficiency", "training_efficiency"
        ]

        with open(features_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for feat in all_features:
                row = {
                    "match_id": feat.match_id,
                    "winner": feat.winner,
                    "reason": feat.reason,
                    "total_turns": feat.total_turns,
                    "opening_turn_1": feat.opening_turn_1,
                    "opening_turn_2": feat.opening_turn_2,
                    "opening_turn_3": feat.opening_turn_3,
                    "opening_turn_4": feat.opening_turn_4,
                    "opening_turn_5": feat.opening_turn_5,
                    "opening_turn_6": feat.opening_turn_6,
                    "opening_turn_7": feat.opening_turn_7,
                    "opening_turn_8": feat.opening_turn_8,
                    "opening_turn_9": feat.opening_turn_9,
                    "opening_turn_10": feat.opening_turn_10,
                    "first_train_turn": feat.first_train_turn,
                    "train_count": feat.train_count,
                    "first_damage_turn": feat.first_damage_turn,
                    "first_combat_turn": feat.first_combat_turn,
                    "first_turret_turn": feat.first_turret_turn,
                    "first_hunger_turn": feat.first_hunger_turn,
                    "total_damage_combat": feat.total_damage_combat,
                    "total_damage_turret": feat.total_damage_turret,
                    "total_damage_hunger": feat.total_damage_hunger,
                    "first_siege_turn": feat.first_siege_turn,
                    "total_siege_damage": feat.total_siege_damage,
                    "siege_count": feat.siege_count,
                    "avg_time_left": feat.avg_time_left,
                    "avg_time_right": feat.avg_time_right,
                    "total_moves": feat.total_moves,
                    "avg_moves_per_turn": feat.avg_moves_per_turn,
                    "hunger_index": feat.hunger_index,
                    "turret_risk": feat.turret_risk,
                    "siege_efficiency": feat.siege_efficiency,
                    "training_efficiency": feat.training_efficiency
                }
                writer.writerow(row)


# =============================================================================
# 메인 함수
# =============================================================================

def main():
    """
    analyze_logs.py 메인 실행 함수
    STEP2: 로그 분석 → 이벤트 → 패턴 → Feature Vector
    """
    project_root = Path(__file__).parent.parent
    raw_dir = project_root / "logs" / "raw"
    analysis_dir = project_root / "logs" / "analysis"

    print("=== NYPC AI 전략 분석 플랫폼 (STEP 2) ===")

    # 로그 파일 찾기
    log_files = sorted(raw_dir.glob("game_*.log"))
    print(f"발견된 로그 파일: {len(log_files)}개")

    if not log_files:
        print("로그 파일이 없습니다. 먼저 run_matches.py를 실행하세요.")
        return

    # 분석기 초기화
    exporter = Exporter(analysis_dir)
    all_features = []

    # 각 경기 분석
    for log_file in log_files:
        # match_id 추출
        filename = log_file.name
        if filename.startswith("game_") and filename.endswith(".log"):
            match_id_str = filename[5:-4]
            try:
                match_id = int(match_id_str)
            except ValueError:
                continue
        else:
            continue

        print(f"경기 {match_id} 분석 중...")

        # 분석 파이프라인
        events = LogParser.parse_log(log_file, match_id)
        tracked = EventTracker.track(events)
        metrics = MetricExtractor.extract(events)
        patterns = PatternExtractor.extract(events, tracked, metrics)
        features = FeatureExtractor.extract(metrics, patterns)
        map_analysis = MapAnalyzer.analyze(tracked.map_data, patterns)

        # 내보내기
        exporter.export_match(match_id, events, tracked, metrics, patterns, features, map_analysis)
        all_features.append(features)

        print(f"경기 {match_id} 분석 완료")

    # 전체 요약 내보내기
    exporter.export_summary(all_features)
    print(f"\n분석 완료!")
    print(f"결과가 {analysis_dir}에 저장되었습니다.")
    print(f" - features.csv: STEP3에서 직접 사용 가능한 Feature Vector")
    print(f" - match_XXXX/: 각 경기별 상세 분석 결과")


if __name__ == "__main__":
    main()

