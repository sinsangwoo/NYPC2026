#!/usr/bin/env python3
"""
NYPC AI 전략 분석 플랫폼 - STEP 2 (업그레이드 버전!)
로그 분석, 패턴 추출, Feature Vector 생성
사용자 피드백 반영:
1. 시간축(Time Series) Feature
2. 이벤트 기반 Opening Signature
3. 그래프 이론 기반 Map Analyzer
4. Warrior Path 사망 추정
5. train_count_before_first_siege
"""

import json
import csv
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Set
from collections import defaultdict, Counter


# =============================================================================
# 1. Parser 모듈: 로그 → 이벤트
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
# 2. Event Tracker 모듈: 턴별 이벤트 정리 + Time Series
# =============================================================================

@dataclass
class WarriorTrack:
    warrior_id: str
    path: List[Tuple[int, int]]  # (turn, region)
    created_turn: Optional[int] = None
    last_seen_turn: Optional[int] = None  # 마지막으로 보인 턴
    is_presumed_dead: bool = False  # 추정 사망 여부


@dataclass
class TimeSeriesData:
    """시간축 데이터 - 각 턴마다의 행동 개수"""
    turns: List[int]
    move_count: Dict[int, int]  # turn -> move 개수
    train_count: Dict[int, int]  # turn -> train 개수
    damage_combat: Dict[int, int]  # turn -> combat 데미지
    damage_turret: Dict[int, int]  # turn -> turret 데미지
    damage_hunger: Dict[int, int]  # turn -> hunger 데미지
    siege_count: Dict[int, int]  # turn -> siege 횟수
    siege_damage: Dict[int, int]  # turn -> siege 데미지


@dataclass
class TrackedEvents:
    match_id: int
    map_data: MapData
    turns: List[int]
    warriors: Dict[str, WarriorTrack]
    result: Optional[ResultEvent]
    time_series: TimeSeriesData


class EventTracker:
    """이벤트를 턴별로 추적하고 정리 + Time Series 생성"""

    @staticmethod
    def track(events: MatchEvents) -> TrackedEvents:
        turns = sorted(events.commands.keys())
        max_turn = max(turns) if turns else 0

        # Time Series 초기화
        time_series = TimeSeriesData(
            turns=turns,
            move_count=defaultdict(int),
            train_count=defaultdict(int),
            damage_combat=defaultdict(int),
            damage_turret=defaultdict(int),
            damage_hunger=defaultdict(int),
            siege_count=defaultdict(int),
            siege_damage=defaultdict(int)
        )

        # Warriors 초기화
        warriors = {}
        # 초기 전사 (A1-A3, B1-B3)
        for side in ["A", "B"]:
            for num in [1, 2, 3]:
                wid = f"{side}{num}"
                warriors[wid] = WarriorTrack(
                    warrior_id=wid,
                    path=[],
                    created_turn=0
                )

        # 턴별 이벤트 추적
        for turn in turns:
            # Time Series 데이터 채우기
            if turn in events.moves:
                time_series.move_count[turn] = len(events.moves[turn])

            if turn in events.trains:
                time_series.train_count[turn] = len(events.trains[turn].warrior_ids)

            if turn in events.damages:
                for dmg in events.damages[turn]:
                    if dmg.cause == "COMBAT":
                        time_series.damage_combat[turn] += dmg.amount
                    elif dmg.cause == "TURRET":
                        time_series.damage_turret[turn] += dmg.amount
                    elif dmg.cause == "HUNGER":
                        time_series.damage_hunger[turn] += dmg.amount

            if turn in events.sieges:
                time_series.siege_count[turn] = len(events.sieges[turn])
                for siege in events.sieges[turn]:
                    time_series.siege_damage[turn] += siege.damage

            # TRAIN으로 새 전사 추가
            if turn in events.trains and events.trains[turn].warrior_ids:
                for wid in events.trains[turn].warrior_ids:
                    if wid not in warriors:
                        warriors[wid] = WarriorTrack(
                            warrior_id=wid,
                            path=[],
                            created_turn=turn
                        )

            # MOVE로 전사 위치 업데이트
            if turn in events.moves:
                for move in events.moves[turn]:
                    wid = move.warrior_id
                    if wid in warriors:
                        warriors[wid].path.append((turn, move.region))
                        warriors[wid].last_seen_turn = turn

        # 사망 추정: 마지막으로 보인 턴이 마지막 턴보다 5턴 이상 전이면 추정 사망
        for wid, track in warriors.items():
            if track.last_seen_turn is not None and (max_turn - track.last_seen_turn) > 5:
                track.is_presumed_dead = True
            elif track.last_seen_turn is None:
                # 한 번도 움직이지 않았으면 초기 위치에 계속 있음
                track.is_presumed_dead = False
            else:
                track.is_presumed_dead = False

        return TrackedEvents(
            match_id=events.match_id,
            map_data=events.map_data,
            turns=turns,
            warriors=warriors,
            result=events.result,
            time_series=time_series
        )


# =============================================================================
# 3. Metric Extractor 모듈: 순수 수치 추출
# =============================================================================

@dataclass
class Metrics:
    # 경기 기본 정보
    match_id: int
    winner: str
    reason: str
    total_turns: int

    # 첫 이벤트 턴
    first_train_turn: Optional[int]
    first_damage_turn: Optional[int]
    first_combat_turn: Optional[int]
    first_turret_turn: Optional[int]
    first_hunger_turn: Optional[int]
    first_siege_turn: Optional[int]

    # TRAIN 관련
    train_count: int
    train_count_before_first_siege: int  # 첫 SIEGE 전까지 TRAIN 횟수
    trained_units: List[str]

    # DAMAGE 관련
    total_damage_combat: int
    total_damage_turret: int
    total_damage_hunger: int

    # SIEGE 관련
    total_siege_damage: int
    siege_count: int
    sieged_regions: Set[int]

    # 시간 관련
    avg_time_left: float
    avg_time_right: float

    # 이동 관련
    total_moves: int
    avg_moves_per_turn: float

    # 전사 관련
    total_warriors: int
    presumed_dead_count: int


class MetricExtractor:
    """이벤트에서 수치 메트릭 추출"""

    @staticmethod
    def extract(events: MatchEvents, tracked: TrackedEvents) -> Metrics:
        turns = sorted(events.commands.keys())
        total_turns = max(turns) if turns else 0

        # 첫 이벤트 찾기
        first_train_turn = None
        first_damage_turn = None
        first_combat_turn = None
        first_turret_turn = None
        first_hunger_turn = None
        first_siege_turn = None

        # TRAIN 메트릭
        train_count = 0
        trained_units = []
        all_train_turns = []
        for turn in sorted(events.trains.keys()):
            train = events.trains[turn]
            if train.warrior_ids:
                if first_train_turn is None:
                    first_train_turn = turn
                train_count += len(train.warrior_ids)
                trained_units.extend(train.warrior_ids)
                all_train_turns.append(turn)

        # DAMAGE 메트릭
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

        # train_count_before_first_siege 계산
        train_count_before_first_siege = 0
        if first_siege_turn is not None:
            for turn in all_train_turns:
                if turn < first_siege_turn:
                    # 이 턴의 TRAIN 개수 세기
                    if turn in events.trains:
                        train_count_before_first_siege += len(events.trains[turn].warrior_ids)

        # 시간 메트릭
        times = list(events.times.values())
        avg_time_left = sum(t.left_time for t in times) / len(times) if times else 0
        avg_time_right = sum(t.right_time for t in times) / len(times) if times else 0

        # 이동 메트릭
        total_moves = sum(len(moves) for moves in events.moves.values())
        avg_moves_per_turn = total_moves / total_turns if total_turns > 0 else 0

        # 전사 메트릭
        total_warriors = len(tracked.warriors)
        presumed_dead_count = sum(1 for w in tracked.warriors.values() if w.is_presumed_dead)

        winner = events.result.winner if events.result else "UNKNOWN"
        reason = events.result.reason if events.result else "UNKNOWN"

        return Metrics(
            match_id=events.match_id,
            winner=winner,
            reason=reason,
            total_turns=total_turns,
            first_train_turn=first_train_turn,
            first_damage_turn=first_damage_turn,
            first_combat_turn=first_combat_turn,
            first_turret_turn=first_turret_turn,
            first_hunger_turn=first_hunger_turn,
            first_siege_turn=first_siege_turn,
            train_count=train_count,
            train_count_before_first_siege=train_count_before_first_siege,
            trained_units=trained_units,
            total_damage_combat=total_damage_combat,
            total_damage_turret=total_damage_turret,
            total_damage_hunger=total_damage_hunger,
            total_siege_damage=total_siege_damage,
            siege_count=siege_count,
            sieged_regions=sieged_regions,
            avg_time_left=avg_time_left,
            avg_time_right=avg_time_right,
            total_moves=total_moves,
            avg_moves_per_turn=avg_moves_per_turn,
            total_warriors=total_warriors,
            presumed_dead_count=presumed_dead_count
        )


# =============================================================================
# 4. Pattern Extractor 모듈: 행동 패턴 추출
# =============================================================================

@dataclass
class EventBasedOpening:
    """이벤트 기반 Opening Signature"""
    event_sequence: List[Tuple[str, int]]  # (event_type, turn)
    # event_type: "FIRST_MOVE", "FIRST_TRAIN", "FIRST_DAMAGE", "FIRST_COMBAT", "FIRST_SIEGE"


@dataclass
class MovementPattern:
    node_visits: Counter[int]
    edge_traffic: Counter[Tuple[int, int]]
    warrior_paths: Dict[str, List[Tuple[int, int, bool]]]  # (turn, region, is_presumed_dead)


@dataclass
class Patterns:
    opening: EventBasedOpening
    movement: MovementPattern
    time_series: TimeSeriesData


class PatternExtractor:
    """이벤트에서 행동 패턴 추출"""

    @staticmethod
    def extract(events: MatchEvents, tracked: TrackedEvents, metrics: Metrics) -> Patterns:
        # 이벤트 기반 Opening Signature
        event_sequence = []
        if metrics.first_train_turn is not None:
            event_sequence.append(("FIRST_TRAIN", metrics.first_train_turn))
        if metrics.first_damage_turn is not None:
            event_sequence.append(("FIRST_DAMAGE", metrics.first_damage_turn))
        if metrics.first_combat_turn is not None:
            event_sequence.append(("FIRST_COMBAT", metrics.first_combat_turn))
        if metrics.first_turret_turn is not None:
            event_sequence.append(("FIRST_TURRET", metrics.first_turret_turn))
        if metrics.first_hunger_turn is not None:
            event_sequence.append(("FIRST_HUNGER", metrics.first_hunger_turn))
        if metrics.first_siege_turn is not None:
            event_sequence.append(("FIRST_SIEGE", metrics.first_siege_turn))
        # 턴 순서로 정렬
        event_sequence.sort(key=lambda x: x[1])

        opening = EventBasedOpening(
            event_sequence=event_sequence
        )

        # Movement 패턴
        node_visits = Counter()
        edge_traffic = Counter()
        warrior_paths = {}

        for wid, track in tracked.warriors.items():
            path_with_info = []
            prev_region = None
            for turn, region in track.path:
                node_visits[region] += 1
                if prev_region is not None and prev_region != region:
                    edge_traffic[(prev_region, region)] += 1
                path_with_info.append((turn, region, track.is_presumed_dead))
                prev_region = region
            warrior_paths[wid] = path_with_info

        movement = MovementPattern(
            node_visits=node_visits,
            edge_traffic=edge_traffic,
            warrior_paths=warrior_paths
        )

        return Patterns(
            opening=opening,
            movement=movement,
            time_series=tracked.time_series
        )


# =============================================================================
# 5. Map Analyzer 모듈: 그래프 이론 기반 분석
# =============================================================================

@dataclass
class GraphMetrics:
    degree: Dict[int, int]  # 노드 -> 차수
    betweenness_centrality: Dict[int, float]  # 노드 -> 매개 중심성 (간단 버전)
    stronghold_degree: Dict[int, int]  # 요새 -> 차수
    is_bridge: Dict[Tuple[int, int], bool]  # (u, v) -> 다리 여부 (간단 버전)


@dataclass
class MapAnalysis:
    transition_matrix: Dict[str, Dict[str, int]]
    node_visits: Dict[int, int]
    stronghold_visits: Dict[int, int]
    graph_metrics: GraphMetrics


class MapAnalyzer:
    """맵과 이동 패턴 분석 + 그래프 이론 적용"""

    @staticmethod
    def analyze(map_data: MapData, patterns: Patterns) -> MapAnalysis:
        # Transition Matrix
        transition_matrix = defaultdict(lambda: defaultdict(int))
        for (u, v), count in patterns.movement.edge_traffic.items():
            transition_matrix[str(u)][str(v)] = count

        # Node visits
        node_visits = dict(patterns.movement.node_visits)

        # Stronghold visits
        stronghold_visits = {}
        for stronghold in map_data.strongholds:
            stronghold_visits[stronghold] = node_visits.get(stronghold, 0)

        # 그래프 메트릭
        graph_metrics = MapAnalyzer._compute_graph_metrics(map_data)

        return MapAnalysis(
            transition_matrix=dict(transition_matrix),
            node_visits=node_visits,
            stronghold_visits=stronghold_visits,
            graph_metrics=graph_metrics
        )

    @staticmethod
    def _compute_graph_metrics(map_data: MapData) -> GraphMetrics:
        degree = {}
        betweenness_centrality = {}
        is_bridge = {}

        # 1. Degree 계산
        for u in range(map_data.N):
            degree[u] = len(map_data.adj[u])

        # 2. Stronghold Degree
        stronghold_degree = {}
        for stronghold in map_data.strongholds:
            stronghold_degree[stronghold] = degree.get(stronghold, 0)

        # 3. 간단한 Betweenness Centrality (노드가 몇 개의 최단 경로에 있는지 - 근사값)
        # 여기서는 간단하게 "얼마나 많은 노드와 연결되어 있는지"로 대체
        for u in range(map_data.N):
            # 간단 버전: (degree * (전체 노드 - degree)) 로 대략적인 중심성 계산
            betweenness_centrality[u] = degree[u] * (map_data.N - degree[u])

        # 4. Bridge 여부 (간단 버전: 한쪽 노드의 차수가 1이면 Bridge로 간주)
        for u in range(map_data.N):
            for v in map_data.adj[u]:
                if u < v:  # 중복 체크 방지
                    if degree[u] == 1 or degree[v] == 1:
                        is_bridge[(u, v)] = True
                    else:
                        is_bridge[(u, v)] = False

        return GraphMetrics(
            degree=degree,
            betweenness_centrality=betweenness_centrality,
            stronghold_degree=stronghold_degree,
            is_bridge=is_bridge
        )


# =============================================================================
# 6. Feature Extractor 모듈: Feature Vector 생성
# =============================================================================

@dataclass
class Features:
    # 경기 기본
    match_id: int
    winner: int  # -1=DRAW, 0=LEFT, 1=RIGHT
    reason: str
    total_turns: int

    # 첫 이벤트
    first_train_turn: float
    first_damage_turn: float
    first_combat_turn: float
    first_turret_turn: float
    first_hunger_turn: float
    first_siege_turn: float

    # TRAIN
    train_count: int
    train_count_before_first_siege: int

    # DAMAGE
    total_damage_combat: int
    total_damage_turret: int
    total_damage_hunger: int

    # SIEGE
    total_siege_damage: int
    siege_count: int

    # 시간
    avg_time_left: float
    avg_time_right: float

    # 이동
    total_moves: int
    avg_moves_per_turn: float

    # 전사
    total_warriors: int
    presumed_dead_count: int

    # 게임 메커니즘 지표
    hunger_index: int
    turret_risk: float
    siege_efficiency: float

    # 이벤트 기반 Opening (1=발생, 0=없음)
    opening_has_train: int
    opening_has_damage: int
    opening_has_combat: int
    opening_has_turret: int
    opening_has_hunger: int
    opening_has_siege: int
    opening_first_event_turn: float


class FeatureExtractor:
    """메트릭과 패턴에서 Feature Vector 생성"""

    @staticmethod
    def extract(metrics: Metrics, patterns: Patterns) -> Features:
        # Winner 인코딩
        winner = -1
        if metrics.winner == "LEFT_WIN":
            winner = 0
        elif metrics.winner == "RIGHT_WIN":
            winner = 1

        # 게임 메커니즘 지표
        hunger_index = metrics.total_damage_hunger

        total_damage = metrics.total_damage_combat + metrics.total_damage_turret + metrics.total_damage_hunger
        turret_risk = metrics.total_damage_turret / total_damage if total_damage > 0 else 0.0

        siege_efficiency = 0.0
        if metrics.total_damage_combat > 0:
            siege_efficiency = metrics.total_siege_damage / metrics.total_damage_combat

        # 이벤트 기반 Opening Feature
        opening_has_train = 1 if metrics.first_train_turn is not None else 0
        opening_has_damage = 1 if metrics.first_damage_turn is not None else 0
        opening_has_combat = 1 if metrics.first_combat_turn is not None else 0
        opening_has_turret = 1 if metrics.first_turret_turn is not None else 0
        opening_has_hunger = 1 if metrics.first_hunger_turn is not None else 0
        opening_has_siege = 1 if metrics.first_siege_turn is not None else 0

        first_event_turn = float("inf")
        for etype, eturn in patterns.opening.event_sequence:
            if eturn < first_event_turn:
                first_event_turn = eturn

        return Features(
            match_id=metrics.match_id,
            winner=winner,
            reason=metrics.reason,
            total_turns=metrics.total_turns,
            first_train_turn=metrics.first_train_turn if metrics.first_train_turn else float("inf"),
            first_damage_turn=metrics.first_damage_turn if metrics.first_damage_turn else float("inf"),
            first_combat_turn=metrics.first_combat_turn if metrics.first_combat_turn else float("inf"),
            first_turret_turn=metrics.first_turret_turn if metrics.first_turret_turn else float("inf"),
            first_hunger_turn=metrics.first_hunger_turn if metrics.first_hunger_turn else float("inf"),
            first_siege_turn=metrics.first_siege_turn if metrics.first_siege_turn else float("inf"),
            train_count=metrics.train_count,
            train_count_before_first_siege=metrics.train_count_before_first_siege,
            total_damage_combat=metrics.total_damage_combat,
            total_damage_turret=metrics.total_damage_turret,
            total_damage_hunger=metrics.total_damage_hunger,
            total_siege_damage=metrics.total_siege_damage,
            siege_count=metrics.siege_count,
            avg_time_left=metrics.avg_time_left,
            avg_time_right=metrics.avg_time_right,
            total_moves=metrics.total_moves,
            avg_moves_per_turn=metrics.avg_moves_per_turn,
            total_warriors=metrics.total_warriors,
            presumed_dead_count=metrics.presumed_dead_count,
            hunger_index=hunger_index,
            turret_risk=turret_risk,
            siege_efficiency=siege_efficiency,
            opening_has_train=opening_has_train,
            opening_has_damage=opening_has_damage,
            opening_has_combat=opening_has_combat,
            opening_has_turret=opening_has_turret,
            opening_has_hunger=opening_has_hunger,
            opening_has_siege=opening_has_siege,
            opening_first_event_turn=first_event_turn
        )


# =============================================================================
# 7. Exporter 모듈: 다양한 형식으로 출력
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

        # Patterns (Time Series 포함)
        self._export_patterns(match_dir, patterns)

        # Opening Signature (이벤트 기반)
        self._export_opening_signature(match_dir, patterns)

        # Map Analysis (그래프 메트릭 포함)
        self._export_map_analysis(match_dir, map_analysis)

        # Warrior Tracks (사망 추정 포함)
        self._export_warrior_tracks(match_dir, tracked)

    def export_summary(self, all_features: List[Features]):
        """전체 경기 요약 (STEP3에서 직접 사용할 CSV)"""
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
            "first_damage_turn": metrics.first_damage_turn,
            "first_combat_turn": metrics.first_combat_turn,
            "first_turret_turn": metrics.first_turret_turn,
            "first_hunger_turn": metrics.first_hunger_turn,
            "first_siege_turn": metrics.first_siege_turn,
            "train_count": metrics.train_count,
            "train_count_before_first_siege": metrics.train_count_before_first_siege,
            "trained_units": metrics.trained_units,
            "total_damage_combat": metrics.total_damage_combat,
            "total_damage_turret": metrics.total_damage_turret,
            "total_damage_hunger": metrics.total_damage_hunger,
            "total_siege_damage": metrics.total_siege_damage,
            "siege_count": metrics.siege_count,
            "total_moves": metrics.total_moves,
            "total_warriors": metrics.total_warriors,
            "presumed_dead_count": metrics.presumed_dead_count
        }
        with open(match_dir / "metrics.json", 'w', encoding='utf-8') as f:
            json.dump(metrics_dict, f, indent=2)

    def _export_patterns(self, match_dir: Path, patterns: Patterns):
        patterns_dict = {
            "time_series": {
                "turns": patterns.time_series.turns,
                "move_count": {str(k): v for k, v in patterns.time_series.move_count.items()},
                "train_count": {str(k): v for k, v in patterns.time_series.train_count.items()},
                "damage_combat": {str(k): v for k, v in patterns.time_series.damage_combat.items()},
                "damage_turret": {str(k): v for k, v in patterns.time_series.damage_turret.items()},
                "damage_hunger": {str(k): v for k, v in patterns.time_series.damage_hunger.items()},
                "siege_count": {str(k): v for k, v in patterns.time_series.siege_count.items()},
                "siege_damage": {str(k): v for k, v in patterns.time_series.siege_damage.items()}
            },
            "movement": {
                "node_visits": {str(k): v for k, v in patterns.movement.node_visits.items()},
                "edge_traffic": {f"{u}_{v}": c for (u, v), c in patterns.movement.edge_traffic.items()}
            }
        }
        with open(match_dir / "patterns.json", 'w', encoding='utf-8') as f:
            json.dump(patterns_dict, f, indent=2)

    def _export_opening_signature(self, match_dir: Path, patterns: Patterns):
        signature = {
            "event_based": [
                {"event_type": etype, "turn": eturn}
                for etype, eturn in patterns.opening.event_sequence
            ]
        }
        with open(match_dir / "opening_signature.json", 'w', encoding='utf-8') as f:
            json.dump(signature, f, indent=2)

    def _export_map_analysis(self, match_dir: Path, map_analysis: MapAnalysis):
        map_analysis_dict = {
            "transition_matrix": map_analysis.transition_matrix,
            "node_visits": {str(k): v for k, v in map_analysis.node_visits.items()},
            "stronghold_visits": {str(k): v for k, v in map_analysis.stronghold_visits.items()},
            "graph_metrics": {
                "degree": {str(k): v for k, v in map_analysis.graph_metrics.degree.items()},
                "betweenness_centrality": {str(k): v for k, v in map_analysis.graph_metrics.betweenness_centrality.items()},
                "stronghold_degree": {str(k): v for k, v in map_analysis.graph_metrics.stronghold_degree.items()},
                "is_bridge": {f"{u}_{v}": v for (u, v), v in map_analysis.graph_metrics.is_bridge.items()}
            }
        }
        with open(match_dir / "map_analysis.json", 'w', encoding='utf-8') as f:
            json.dump(map_analysis_dict, f, indent=2)

    def _export_warrior_tracks(self, match_dir: Path, tracked: TrackedEvents):
        warrior_tracks = {}
        for wid, track in tracked.warriors.items():
            warrior_tracks[wid] = {
                "created_turn": track.created_turn,
                "last_seen_turn": track.last_seen_turn,
                "is_presumed_dead": track.is_presumed_dead,
                "path": [{"turn": t, "region": r} for t, r in track.path]
            }
        with open(match_dir / "warrior_tracks.json", 'w', encoding='utf-8') as f:
            json.dump(warrior_tracks, f, indent=2)

    def _export_features_csv(self, features_path: Path, all_features: List[Features]):
        fieldnames = [
            "match_id", "winner", "reason", "total_turns",
            "first_train_turn", "first_damage_turn", "first_combat_turn",
            "first_turret_turn", "first_hunger_turn", "first_siege_turn",
            "train_count", "train_count_before_first_siege",
            "total_damage_combat", "total_damage_turret", "total_damage_hunger",
            "total_siege_damage", "siege_count",
            "avg_time_left", "avg_time_right",
            "total_moves", "avg_moves_per_turn",
            "total_warriors", "presumed_dead_count",
            "hunger_index", "turret_risk", "siege_efficiency",
            "opening_has_train", "opening_has_damage", "opening_has_combat",
            "opening_has_turret", "opening_has_hunger", "opening_has_siege",
            "opening_first_event_turn"
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
                    "first_train_turn": feat.first_train_turn,
                    "first_damage_turn": feat.first_damage_turn,
                    "first_combat_turn": feat.first_combat_turn,
                    "first_turret_turn": feat.first_turret_turn,
                    "first_hunger_turn": feat.first_hunger_turn,
                    "first_siege_turn": feat.first_siege_turn,
                    "train_count": feat.train_count,
                    "train_count_before_first_siege": feat.train_count_before_first_siege,
                    "total_damage_combat": feat.total_damage_combat,
                    "total_damage_turret": feat.total_damage_turret,
                    "total_damage_hunger": feat.total_damage_hunger,
                    "total_siege_damage": feat.total_siege_damage,
                    "siege_count": feat.siege_count,
                    "avg_time_left": feat.avg_time_left,
                    "avg_time_right": feat.avg_time_right,
                    "total_moves": feat.total_moves,
                    "avg_moves_per_turn": feat.avg_moves_per_turn,
                    "total_warriors": feat.total_warriors,
                    "presumed_dead_count": feat.presumed_dead_count,
                    "hunger_index": feat.hunger_index,
                    "turret_risk": feat.turret_risk,
                    "siege_efficiency": feat.siege_efficiency,
                    "opening_has_train": feat.opening_has_train,
                    "opening_has_damage": feat.opening_has_damage,
                    "opening_has_combat": feat.opening_has_combat,
                    "opening_has_turret": feat.opening_has_turret,
                    "opening_has_hunger": feat.opening_has_hunger,
                    "opening_has_siege": feat.opening_has_siege,
                    "opening_first_event_turn": feat.opening_first_event_turn
                }
                writer.writerow(row)


# =============================================================================
# 데이터 품질 검사 모듈
# =============================================================================

@dataclass
class QualityCheckResult:
    total_logs: int
    valid_logs: int
    invalid_logs: list
    issues: list
    parsing_errors: list
    feature_issues: list


class QualityChecker:
    @staticmethod
    def check_log_file(log_file: Path, match_id: int) -> tuple[bool, list]:
        issues = []
        try:
            # 파일 크기 확인
            if log_file.stat().st_size == 0:
                issues.append("빈 파일")
                return False, issues
            
            # 로그 파싱 시도
            events = LogParser.parse_log(log_file, match_id)
            
            # 기본 이벤트 존재 여부 확인
            if not events.result:
                issues.append("결과 정보 없음")
            
            if not events.map_data or events.map_data.N == 0:
                issues.append("맵 데이터 누락")
            
        except Exception as e:
            issues.append(f"파싱 오류: {str(e)}")
            return False, issues
        
        return True, issues
    
    @staticmethod
    def check_features(features: Features) -> list:
        issues = []
        
        # 음수 값 확인
        if features.train_count < 0:
            issues.append("train_count 음수")
        if features.total_damage_combat < 0:
            issues.append("total_damage_combat 음수")
        if features.total_turns < 0:
            issues.append("total_turns 음수")
        
        # NaN/Inf 확인
        import math
        if math.isinf(features.first_damage_turn) and features.first_damage_turn > 0:
            pass  # expected
        elif math.isnan(features.first_damage_turn):
            issues.append("first_damage_turn NaN")
        
        return issues
    
    @staticmethod
    def run_all_checks(log_files: list, all_features: list) -> QualityCheckResult:
        total = len(log_files)
        valid = 0
        invalid_logs = []
        all_issues = []
        parsing_errors = []
        feature_issues_list = []
        
        for i, (log_file, features) in enumerate(zip(log_files, all_features)):
            is_valid, log_issues = QualityChecker.check_log_file(log_file, i + 1)
            feat_issues = QualityChecker.check_features(features)
            
            if log_issues:
                all_issues.extend([f"{log_file.name}: {issue}" for issue in log_issues])
            if feat_issues:
                feature_issues_list.extend([f"{log_file.name}: {issue}" for issue in feat_issues])
            
            if is_valid and not feat_issues:
                valid += 1
            else:
                invalid_logs.append(log_file.name)
        
        return QualityCheckResult(
            total_logs=total,
            valid_logs=valid,
            invalid_logs=invalid_logs,
            issues=all_issues,
            parsing_errors=parsing_errors,
            feature_issues=feature_issues_list
        )


# =============================================================================
# 메인 함수
# =============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="NYPC 로그 분석 툴")
    parser.add_argument("--log-dir", type=str, default="logs/baseline_benchmark",
                        help="로그 파일이 있는 디렉토리")
    parser.add_argument("--analysis-dir", type=str, default="logs/baseline_analysis",
                        help="분석 결과를 저장할 디렉토리")
    
    args = parser.parse_args()
    
    project_root = Path(__file__).parent.parent
    raw_dir = project_root / args.log_dir
    analysis_dir = project_root / args.analysis_dir

    print("=" * 60)
    print("🎮 NYPC AI 전략 분석 플랫폼 - Baseline Benchmark 분석")
    print("=" * 60)

    # 모든 .log 파일 찾기
    log_files = sorted(raw_dir.glob("*.log"))
    print(f"발견된 로그 파일: {len(log_files)}개")

    if not log_files:
        print("로그 파일이 없습니다. 먼저 run_matches.py를 실행하세요.")
        return

    exporter = Exporter(analysis_dir)
    all_features = []
    all_events = []
    all_tracked = []

    for i, log_file in enumerate(log_files):
        filename = log_file.name
        match_id = i + 1  # 단순히 순서대로 ID 할당
        
        print(f"경기 {match_id}/{len(log_files)} 분석 중... ({filename})")

        try:
            # 분석 파이프라인
            events = LogParser.parse_log(log_file, match_id)
            tracked = EventTracker.track(events)
            metrics = MetricExtractor.extract(events, tracked)
            patterns = PatternExtractor.extract(events, tracked, metrics)
            features = FeatureExtractor.extract(metrics, patterns)
            map_analysis = MapAnalyzer.analyze(tracked.map_data, patterns)

            exporter.export_match(match_id, events, tracked, metrics, patterns, features, map_analysis)
            all_features.append(features)
            all_events.append(events)
            all_tracked.append(tracked)

            print(f"경기 {match_id} 분석 완료")
        except Exception as e:
            print(f"경기 {match_id} 분석 오류: {e}")

    # 요약 내보내기
    exporter.export_summary(all_features)
    
    # 품질 검사 실행
    print()
    print("=" * 60)
    print("🔍 데이터 품질 검사 실행 중...")
    print("=" * 60)
    qc_result = QualityChecker.run_all_checks(log_files, all_features)
    
    print(f"총 로그: {qc_result.total_logs}")
    print(f"유효한 로그: {qc_result.valid_logs}")
    print(f"문제가 있는 로그: {len(qc_result.invalid_logs)}")
    
    if qc_result.issues:
        print("\n문제 사항:")
        for issue in qc_result.issues[:10]:  # 최대 10개만 표시
            print(f"  - {issue}")
        if len(qc_result.issues) > 10:
            print(f"  ... 외 {len(qc_result.issues) - 10}개")
    
    if qc_result.feature_issues:
        print("\nFeature 문제:")
        for issue in qc_result.feature_issues[:10]:
            print(f"  - {issue}")
        if len(qc_result.feature_issues) > 10:
            print(f"  ... 외 {len(qc_result.feature_issues) - 10}개")
    
    # 벤치마크 요약 보고서 생성
    print()
    print("=" * 60)
    print("📊 벤치마크 요약")
    print("=" * 60)
    
    # 경기 결과 집계
    wins_left = 0
    wins_right = 0
    draws = 0
    turn_limit_draws = 0
    total_turns = []
    
    for events in all_events:
        if events.result:
            winner = events.result.winner
            reason = events.result.reason
            if winner == "LEFT_WIN":
                wins_left += 1
            elif winner == "RIGHT_WIN":
                wins_right += 1
            else:
                draws += 1
            if reason == "TURN_LIMIT":
                turn_limit_draws += 1
        if events.commands:
            total_turns.append(max(events.commands.keys()))
    
    print(f"LEFT 승리: {wins_left}")
    print(f"RIGHT 승리: {wins_right}")
    print(f"무승부: {draws}")
    print(f"  - 턴 제한 무승부: {turn_limit_draws}")
    
    if total_turns:
        print(f"평균 턴 수: {sum(total_turns) / len(total_turns):.1f}")
        print(f"최소 턴 수: {min(total_turns)}")
        print(f"최대 턴 수: {max(total_turns)}")
    
    print()
    print("=" * 60)
    print("분석 완료!")
    print("=" * 60)
    print(f"결과가 {analysis_dir}에 저장되었습니다.")


if __name__ == "__main__":
    main()
