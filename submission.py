#!/usr/bin/env python3
from __future__ import annotations


# --- BEGIN action_selector.py ---

"""
Action Selector Module for NYPC 2026 AI
Selects the best candidate actions based on scores
"""
import math
import sys
import json


class ActionSelector:
    def __init__(self, eval_fn: EvaluationFunction):
        self.eval_fn = eval_fn

    def _get_phase_weights(self, turn: int):
        """
        Turn Phase에 따른 Weight 변경 Hook
        현재는 구현하지 않고 기본 Weight 반환
        """
        # TODO: Weight Schedule 구현 시 여기에 로직 추가
        return self.eval_fn.weights

    def select_best_actions(
        self, S: GameState, M: GameMap, P: Paths, turn: int
    ) -> Actions:
        candidates = CandidateGenerator.generate_all_candidates(S, M, P)
        best_score = -math.inf
        best_actions = candidates[0]

        # Debug: Feature Distribution과 Final Score Distribution 수집
        feature_distribution = {
            "turns_to_enemy_hq": [],
            "adj_allies_count": [],
            "adj_enemies_count": [],
            "train_n": [],
            "is_stronghold": []
        }
        final_score_distribution = []

        # Debug: Print all candidates
        debug_data = {
            "turn": turn,
            "candidates": [],
            "feature_distribution": feature_distribution,
            "final_score_distribution": final_score_distribution
        }

        for idx, candidate in enumerate(candidates):
            # Check if candidate is affordable
            total_cost = self._calculate_candidate_cost(S, M, P, candidate)
            affordable = S.gold >= total_cost
            
            score = 0.0
            if affordable:
                # Phase에 맞는 Weight 적용 (Hook)
                original_weights = self.eval_fn.weights
                self.eval_fn.weights = self._get_phase_weights(turn)
                
                score = self.eval_fn.evaluate_actions(S, M, P, candidate, turn)
                
                # Weight 복원
                self.eval_fn.weights = original_weights
                
                # Prefer doing something to doing nothing
                if candidate.train_n > 0 or candidate.moves or candidate.upgrades:
                    score += 0.1

            # Collect candidate data
            candidate_data = {
                "idx": idx,
                "train_n": candidate.train_n,
                "moves": [f"{wid}->{target}" for wid, target in candidate.moves],
                "upgrades": candidate.upgrades,
                "cost": total_cost,
                "affordable": affordable,
                "score": score
            }
            debug_data["candidates"].append(candidate_data)
            
            # Final Score Distribution 수집
            final_score_distribution.append({
                "idx": idx,
                "score": score
            })

            if affordable and score > best_score:
                best_score = score
                best_actions = candidate

        # Debug: Print best action
        debug_data["best_idx"] = candidates.index(best_actions)
        debug_data["best_score"] = best_score
        print(json.dumps(debug_data), file=sys.stderr)
        sys.stderr.flush()

        return best_actions

    @staticmethod
    def _calculate_candidate_cost(
        S: GameState, M: GameMap, P: Paths, actions: Actions
    ) -> int:
        total_cost = 0

        # Calculate move costs
        for wid, target in actions.moves:
            target_building = S.find_building(target)
            cost = 0 if (target_building and target_building.side == M.my_side) else MOVE_COST
            total_cost += cost

        # Calculate train costs
        total_cost += TRAIN_COST * actions.train_n

        # Calculate upgrade costs
        for region in actions.upgrades:
            target_building = S.find_building(region)
            if target_building is None:
                cost = BASE_LEVELS[1].cost
            elif target_building.type == BType.HQ:
                max_level = len(HQ_LEVELS) - 1
                if target_building.level < max_level:
                    cost = target_building.upgrade_cost()
                else:
                    cost = 1000
            else:
                max_level = len(BASE_LEVELS) - 1
                if target_building.level < max_level:
                    cost = target_building.upgrade_cost()
                else:
                    cost = 500
            total_cost += cost

        return total_cost
# --- END action_selector.py ---

# --- BEGIN candidate_generator.py ---

"""
Candidate Action Generator Module for NYPC 2026 AI
Generates possible candidate actions for the AI
"""
from dataclasses import dataclass
from typing import Union, NamedTuple


class CandidateMove(NamedTuple):
    warrior_id: WarriorId
    target_region: int


class CandidateTrain(NamedTuple):
    train_n: int


class CandidateUpgrade(NamedTuple):
    region: int


CandidateAction = Union[CandidateMove, CandidateTrain, CandidateUpgrade]


class CandidateGenerator:
    @staticmethod
    def generate_all_candidates(S: GameState, M: GameMap, P: Paths) -> list[Actions]:
        """
        Generate candidate actions as list of Actions instances.
        Each Actions instance represents a set of actions for one turn.
        """
        candidates: list[Actions] = []

        # Candidate: Do nothing
        candidates.append(Actions())

        # Get stationary warriors
        my_stationary_warriors = [
            w for w in S.warriors
            if w.id.side == M.my_side and w.state == WState.STATIONARY
        ]

        # Generate move candidates for each warrior
        if my_stationary_warriors:
            for warrior in my_stationary_warriors:
                for adj in M.adj[warrior.region]:
                    move_candidate = Actions()
                    move_candidate.moves.append((warrior.id, adj))
                    candidates.append(move_candidate)
                # Wait (no move) candidate already in "Do nothing"
            # Also generate candidate where all warriors move towards enemy HQ
            all_hq_move = Actions()
            for w in my_stationary_warriors:
                next_step = P.nxt[w.region][M.opp_hq]
                if next_step != -1:
                    all_hq_move.moves.append((w.id, next_step))
            candidates.append(all_hq_move)

        # Generate train candidates
        my_hq = S.find_building(M.my_hq)
        if my_hq and my_hq.level > 0:
            train_cap = HQ_LEVELS[my_hq.level].train_cap
            for n in range(0, min(train_cap, S.gold // TRAIN_COST) + 1):
                if n > 0:
                    train_candidate = Actions()
                    train_candidate.train_n = n
                    candidates.append(train_candidate)

        # Generate upgrade candidates
        # Strongholds without buildings
        for sh in M.strongholds:
            if S.find_building(sh) is None and S.gold >= BASE_LEVELS[1].cost:
                has_allies = any(w.region == sh and w.id.side == M.my_side for w in S.warriors)
                has_enemies = any(w.region == sh and w.id.side != M.my_side for w in S.warriors)
                if has_allies and not has_enemies:
                    upgrade_candidate = Actions()
                    upgrade_candidate.upgrades.append(sh)
                    candidates.append(upgrade_candidate)
        # Own buildings to upgrade
        for b in S.buildings:
            if b.side == M.my_side:
                max_level = HQ_MAX_LEVEL if b.type == BType.HQ else BASE_MAX_LEVEL
                if b.level < max_level and S.gold >= b.upgrade_cost():
                    upgrade_candidate = Actions()
                    upgrade_candidate.upgrades.append(b.region)
                    candidates.append(upgrade_candidate)

        return candidates
# --- END candidate_generator.py ---

# --- BEGIN evaluation_function.py ---

"""
Evaluation Function Module for NYPC 2026 AI
Calculates scores for candidate actions using features
"""
import math
import sys
import json
from dataclasses import dataclass


@dataclass
class Weights:
    # Move weights
    w_turns_to_enemy_hq: float = -1.0  # turns_to_enemy_hq가 적을수록 좋음
    w_adj_allies_count: float = 2.0
    w_adj_enemies_count: float = -10.0
    w_is_stronghold: float = 1.0
    w_is_on_hq: float = 1000.0
    w_is_hq_adjacent: float = 500.0
    w_move_cost: float = -10.0  # move_cost가 True이면 나쁨
    w_turns_remaining: float = 0.0
    w_remaining_gold_after_action: float = 10.0

    # Train weights
    w_train_n: float = 50.0
    w_train_cost: float = -10.0
    w_train_remaining_gold: float = 10.0
    w_train_turns_remaining: float = 0.0

    # Upgrade weights
    w_upgrade_is_stronghold: float = 200.0
    w_upgrade_cost: float = -10.0
    w_upgrade_remaining_gold: float = 10.0
    w_upgrade_turns_remaining: float = 0.0


class EvaluationFunction:
    def __init__(self, weights: Weights = Weights()):
        self.weights = weights

    def evaluate_move(self, features: MoveFeatures) -> float:
        # Feature Extraction (raw features)
        f_turns_to_enemy_hq = features.turns_to_enemy_hq
        f_adj_allies_count = features.adj_allies_count
        f_adj_enemies_count = features.adj_enemies_count
        f_is_stronghold = features.is_stronghold
        f_is_on_hq = features.is_on_hq
        f_is_hq_adjacent = features.is_hq_adjacent
        f_move_cost = features.move_cost
        f_turns_remaining = features.turns_remaining
        f_remaining_gold_after_action = features.remaining_gold_after_action

        # Feature Transformation
        # turns_to_enemy_hq: (200 - turns) / 200 → 적을수록 높은 값
        t_turns_to_enemy_hq = (200.0 - f_turns_to_enemy_hq) / 200.0
        t_adj_allies_count = f_adj_allies_count
        t_adj_enemies_count = f_adj_enemies_count
        t_is_stronghold = 1.0 if f_is_stronghold else 0.0
        t_is_on_hq = 1.0 if f_is_on_hq else 0.0
        t_is_hq_adjacent = 1.0 if f_is_hq_adjacent else 0.0
        t_move_cost = 1.0 if f_move_cost else 0.0
        t_turns_remaining = f_turns_remaining
        t_remaining_gold_after_action = max(0.0, f_remaining_gold_after_action)  # 음수 제한

        # Contribution 계산 (개별 변수)
        contrib_turns_to_enemy_hq = self.weights.w_turns_to_enemy_hq * t_turns_to_enemy_hq
        contrib_adj_allies_count = self.weights.w_adj_allies_count * t_adj_allies_count
        contrib_adj_enemies_count = self.weights.w_adj_enemies_count * t_adj_enemies_count
        contrib_is_stronghold = self.weights.w_is_stronghold * t_is_stronghold
        contrib_is_on_hq = self.weights.w_is_on_hq * t_is_on_hq
        contrib_is_hq_adjacent = self.weights.w_is_hq_adjacent * t_is_hq_adjacent
        contrib_move_cost = self.weights.w_move_cost * t_move_cost
        contrib_turns_remaining = self.weights.w_turns_remaining * t_turns_remaining
        contrib_remaining_gold_after_action = self.weights.w_remaining_gold_after_action * t_remaining_gold_after_action

        # Score = Sum of Contributions
        score = (
            contrib_turns_to_enemy_hq +
            contrib_adj_allies_count +
            contrib_adj_enemies_count +
            contrib_is_stronghold +
            contrib_is_on_hq +
            contrib_is_hq_adjacent +
            contrib_move_cost +
            contrib_turns_remaining +
            contrib_remaining_gold_after_action
        )

        # Debug: Print move evaluation (Feature Dump, Contribution Dump, Final Score Dump)
        debug_data = {
            "type": "move",
            "feature_dump": {
                "turns_to_enemy_hq": f_turns_to_enemy_hq,
                "adj_allies_count": f_adj_allies_count,
                "adj_enemies_count": f_adj_enemies_count,
                "is_stronghold": f_is_stronghold,
                "is_on_hq": f_is_on_hq,
                "is_hq_adjacent": f_is_hq_adjacent,
                "move_cost": f_move_cost,
                "turns_remaining": f_turns_remaining,
                "remaining_gold_after_action": f_remaining_gold_after_action
            },
            "contribution_dump": {
                "contrib_turns_to_enemy_hq": contrib_turns_to_enemy_hq,
                "contrib_adj_allies_count": contrib_adj_allies_count,
                "contrib_adj_enemies_count": contrib_adj_enemies_count,
                "contrib_is_stronghold": contrib_is_stronghold,
                "contrib_is_on_hq": contrib_is_on_hq,
                "contrib_is_hq_adjacent": contrib_is_hq_adjacent,
                "contrib_move_cost": contrib_move_cost,
                "contrib_turns_remaining": contrib_turns_remaining,
                "contrib_remaining_gold_after_action": contrib_remaining_gold_after_action
            },
            "final_score": score
        }
        print(json.dumps(debug_data), file=sys.stderr)
        sys.stderr.flush()

        return score

    def evaluate_train(self, features: TrainFeatures) -> float:
        # Feature Extraction (raw features)
        f_train_n = features.train_n
        f_train_cost = features.train_cost
        f_turns_remaining = features.turns_remaining
        f_remaining_gold_after_action = features.remaining_gold_after_action

        # Feature Transformation
        t_train_n = f_train_n
        t_train_cost = f_train_cost
        t_turns_remaining = f_turns_remaining
        t_remaining_gold_after_action = max(0.0, f_remaining_gold_after_action)  # 음수 제한

        # Contribution 계산 (개별 변수)
        contrib_train_n = self.weights.w_train_n * t_train_n
        contrib_train_cost = self.weights.w_train_cost * t_train_cost
        contrib_train_turns_remaining = self.weights.w_train_turns_remaining * t_turns_remaining
        contrib_train_remaining_gold = self.weights.w_train_remaining_gold * t_remaining_gold_after_action

        # Score = Sum of Contributions
        score = (
            contrib_train_n +
            contrib_train_cost +
            contrib_train_turns_remaining +
            contrib_train_remaining_gold
        )

        # Debug: Print train evaluation (Feature Dump, Contribution Dump, Final Score Dump)
        debug_data = {
            "type": "train",
            "feature_dump": {
                "train_n": f_train_n,
                "train_cost": f_train_cost,
                "turns_remaining": f_turns_remaining,
                "remaining_gold_after_action": f_remaining_gold_after_action
            },
            "contribution_dump": {
                "contrib_train_n": contrib_train_n,
                "contrib_train_cost": contrib_train_cost,
                "contrib_train_turns_remaining": contrib_train_turns_remaining,
                "contrib_train_remaining_gold": contrib_train_remaining_gold
            },
            "final_score": score
        }
        print(json.dumps(debug_data), file=sys.stderr)
        sys.stderr.flush()

        return score

    def evaluate_upgrade(self, features: UpgradeFeatures) -> float:
        # Feature Extraction (raw features)
        f_upgrade_cost = features.upgrade_cost
        f_is_stronghold = features.is_stronghold
        f_turns_remaining = features.turns_remaining
        f_remaining_gold_after_action = features.remaining_gold_after_action

        # Feature Transformation
        t_is_stronghold = 1.0 if f_is_stronghold else 0.0
        t_upgrade_cost = f_upgrade_cost
        t_turns_remaining = f_turns_remaining
        t_remaining_gold_after_action = max(0.0, f_remaining_gold_after_action)  # 음수 제한

        # Contribution 계산 (개별 변수)
        contrib_upgrade_is_stronghold = self.weights.w_upgrade_is_stronghold * t_is_stronghold
        contrib_upgrade_cost = self.weights.w_upgrade_cost * t_upgrade_cost
        contrib_upgrade_turns_remaining = self.weights.w_upgrade_turns_remaining * t_turns_remaining
        contrib_upgrade_remaining_gold = self.weights.w_upgrade_remaining_gold * t_remaining_gold_after_action

        # Score = Sum of Contributions
        score = (
            contrib_upgrade_is_stronghold +
            contrib_upgrade_cost +
            contrib_upgrade_turns_remaining +
            contrib_upgrade_remaining_gold
        )

        # Debug: Print upgrade evaluation (Feature Dump, Contribution Dump, Final Score Dump)
        debug_data = {
            "type": "upgrade",
            "feature_dump": {
                "is_stronghold": f_is_stronghold,
                "upgrade_cost": f_upgrade_cost,
                "turns_remaining": f_turns_remaining,
                "remaining_gold_after_action": f_remaining_gold_after_action
            },
            "contribution_dump": {
                "contrib_upgrade_is_stronghold": contrib_upgrade_is_stronghold,
                "contrib_upgrade_cost": contrib_upgrade_cost,
                "contrib_upgrade_turns_remaining": contrib_upgrade_turns_remaining,
                "contrib_upgrade_remaining_gold": contrib_upgrade_remaining_gold
            },
            "final_score": score
        }
        print(json.dumps(debug_data), file=sys.stderr)
        sys.stderr.flush()

        return score

    def evaluate_actions(
        self, S: GameState, M: GameMap, P: Paths, actions: Actions, turn: int
    ) -> float:
        total_score = 0.0

        # Evaluate all moves in this action set
        for wid, target in actions.moves:
            warrior = S.find_warrior(wid)
            if warrior:
                features = FeatureCalculator.calculate_move_features(S, M, P, warrior, target, turn)
                total_score += self.evaluate_move(features)

        # Evaluate train in this action set
        if actions.train_n > 0:
            features = FeatureCalculator.calculate_train_features(S, M, P, actions.train_n, turn)
            total_score += self.evaluate_train(features)

        # Evaluate upgrades in this action set
        for region in actions.upgrades:
            features = FeatureCalculator.calculate_upgrade_features(S, M, P, region, turn)
            total_score += self.evaluate_upgrade(features)

        return total_score
# --- END evaluation_function.py ---

# --- BEGIN feature_calculator.py ---

"""
Feature Calculator Module for NYPC 2026 AI
Calculates all required features for Evaluation Function
"""
import math
from dataclasses import dataclass
from typing import NamedTuple


@dataclass
class MoveFeatures:
    turns_to_enemy_hq: int
    adj_allies_count: int
    adj_enemies_count: int
    is_stronghold: bool
    is_hq_adjacent: bool
    is_on_hq: bool
    move_cost: bool  # Binary: True if cost > 0
    turns_remaining: float  # Ratio: (200 - turn) / 200
    remaining_gold_after_action: float  # Ratio: remaining / START_GOLD


@dataclass
class TrainFeatures:
    train_n: int
    train_cost: float  # Ratio: cost / START_GOLD
    turns_remaining: float  # Ratio: (200 - turn) / 200
    remaining_gold_after_action: float  # Ratio: remaining / START_GOLD


@dataclass
class UpgradeFeatures:
    region: int
    upgrade_cost: float  # Ratio: cost / START_GOLD
    is_stronghold: bool
    turns_remaining: float  # Ratio: (200 - turn) / 200
    remaining_gold_after_action: float  # Ratio: remaining / START_GOLD


class FeatureCalculator:
    @staticmethod
    def calculate_move_features(
        S: GameState, M: GameMap, P: Paths,
        warrior: Warrior, target_region: int, turn: int
    ) -> MoveFeatures:
        """Calculate features for a MOVE action."""

        # Turns to enemy HQ (hop distance)
        turns_to_enemy_hq = P.hop_dist[target_region][M.opp_hq]
        if turns_to_enemy_hq >= M.N:  # HOP_INF
            turns_to_enemy_hq = 200  # MAX_TURN

        # Adjacent allies and enemies
        adj_allies_count = 0
        adj_enemies_count = 0
        for w in S.warriors:
            if w.region == target_region:
                if w.id.side == M.my_side:
                    adj_allies_count += 1
                else:
                    adj_enemies_count += 1

        # Stronghold, HQ checks
        is_stronghold = target_region in M.strongholds
        is_hq_adjacent = target_region in M.adj[M.opp_hq]
        is_on_hq = target_region == M.opp_hq

        # Move cost (binary: True if cost > 0)
        target_building = S.find_building(target_region)
        move_cost_val = 0 if (target_building and target_building.side == M.my_side) else MOVE_COST
        move_cost = move_cost_val > 0

        # Remaining turns (ratio)
        turns_remaining = (200 - turn) / 200.0

        # Remaining gold after action (ratio)
        remaining_gold_after_action = (S.gold - move_cost_val) / START_GOLD

        return MoveFeatures(
            turns_to_enemy_hq=turns_to_enemy_hq,
            adj_allies_count=adj_allies_count,
            adj_enemies_count=adj_enemies_count,
            is_stronghold=is_stronghold,
            is_hq_adjacent=is_hq_adjacent,
            is_on_hq=is_on_hq,
            move_cost=move_cost,
            turns_remaining=turns_remaining,
            remaining_gold_after_action=remaining_gold_after_action
        )

    @staticmethod
    def calculate_train_features(
        S: GameState, M: GameMap, P: Paths, train_n: int, turn: int
    ) -> TrainFeatures:
        """Calculate features for a TRAIN action."""

        train_cost_val = TRAIN_COST * train_n
        train_cost = train_cost_val / START_GOLD  # Ratio
        turns_remaining = (200 - turn) / 200.0  # Ratio
        remaining_gold_after_action = (S.gold - train_cost_val) / START_GOLD  # Ratio

        return TrainFeatures(
            train_n=train_n,
            train_cost=train_cost,
            turns_remaining=turns_remaining,
            remaining_gold_after_action=remaining_gold_after_action
        )

    @staticmethod
    def calculate_upgrade_features(
        S: GameState, M: GameMap, P: Paths, region: int, turn: int
    ) -> UpgradeFeatures:
        """Calculate features for an UPGRADE action."""

        target_building = S.find_building(region)
        if target_building is None:
            upgrade_cost_val = BASE_LEVELS[1].cost
        elif target_building.type == BType.HQ:
            max_level = len(HQ_LEVELS) - 1
            if target_building.level < max_level:
                upgrade_cost_val = target_building.upgrade_cost()
            else:
                upgrade_cost_val = 1000  # HQ heal cost
        else:
            max_level = len(BASE_LEVELS) - 1
            if target_building.level < max_level:
                upgrade_cost_val = target_building.upgrade_cost()
            else:
                upgrade_cost_val = 500  # Base heal cost

        upgrade_cost = upgrade_cost_val / START_GOLD  # Ratio
        is_stronghold = region in M.strongholds
        turns_remaining = (200 - turn) / 200.0  # Ratio
        remaining_gold_after_action = (S.gold - upgrade_cost_val) / START_GOLD  # Ratio

        return UpgradeFeatures(
            region=region,
            upgrade_cost=upgrade_cost,
            is_stronghold=is_stronghold,
            turns_remaining=turns_remaining,
            remaining_gold_after_action=remaining_gold_after_action
        )
# --- END feature_calculator.py ---

# --- BEGIN main.py ---

import math
import sys
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import NamedTuple, Any

MAX_TURN = 200          # maximum turn (days)
START_GOLD = 500        # initial gold
START_WARRIORS = 3      # initial warriors
MOVE_COST = 10          # move cost
TRAIN_COST = 120        # train cost
WORK_INCOME = 15        # income per warrior
UPKEEP_PER_WARRIOR = 2  # upkeep per warrior
HQ_MAX_LEVEL = 5        # HQ max level
BASE_MAX_LEVEL = 3      # base max level
HQ_HEAL_COST = 1000     # HQ fix cost
BASE_HEAL_COST = 500    # base fix cost


class HqLevelEntry(NamedTuple):
    upgrade_cost: int
    warrior_hp: int
    hp: int
    turret: int
    train_cap: int
    work_cap: int


class BaseLevelEntry(NamedTuple):
    cost: int
    hp: int
    turret: int
    work_cap: int


HQ_LEVELS: tuple[HqLevelEntry, ...] = (
    HqLevelEntry(0,     0, 0,  0, 0, 0),
    HqLevelEntry(0,     4, 10, 1, 1, 1),
    HqLevelEntry(600,   5, 15, 2, 1, 2),
    HqLevelEntry(1200,  6, 20, 2, 2, 3),
    HqLevelEntry(2400,  7, 25, 3, 2, 4),
    HqLevelEntry(3600,  8, 30, 3, 3, 5),
)
BASE_LEVELS: tuple[BaseLevelEntry, ...] = (
    BaseLevelEntry(0,    0,  0, 0),
    BaseLevelEntry(300,  6, 1, 1),
    BaseLevelEntry(600,  12, 1, 2),
    BaseLevelEntry(1000, 18, 2, 3),
)


class Side(Enum):
    LEFT = "A"
    RIGHT = "B"

    @property
    def opposite(self) -> "Side":
        return Side.RIGHT if self is Side.LEFT else Side.LEFT

    @classmethod
    def from_word(cls, w: str) -> "Side":
        return cls.LEFT if w == "LEFT" else cls.RIGHT

    @classmethod
    def from_char(cls, c: str) -> "Side":
        return cls.LEFT if c == "A" else cls.RIGHT


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

    def __str__(self) -> str:
        return f"{self.side.value}{self.num}"

    @classmethod
    def parse(cls, tok: str) -> "WarriorId":
        assert tok and tok[0] in ("A", "B")
        return cls(Side.from_char(tok[0]), int(tok[1:]))


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

    def current_hp(self) -> int:
        return HQ_LEVELS[self.level].hp if self.type is BType.HQ else BASE_LEVELS[self.level].hp

    def work_cap(self) -> int:
        return HQ_LEVELS[self.level].work_cap if self.type is BType.HQ else BASE_LEVELS[self.level].work_cap

    def apply_upgrade(self) -> None:
        self.level += 1
        self.hp = self.current_hp()

    def upgrade_cost(self) -> int:
        if self.type is BType.HQ:
            return HQ_LEVELS[self.level + 1].upgrade_cost
        else:
            return BASE_LEVELS[self.level + 1].cost


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
    gold: int = START_GOLD
    my_countdown: int = 5
    opp_countdown: int = 5
    warriors: list[Warrior] = field(default_factory=list)
    buildings: list[Building] = field(default_factory=list)

    def find_building(self, region: int) -> Building | None:
        return next((b for b in self.buildings if b.region == region), None)

    def find_warrior(self, wid: WarriorId) -> Warrior | None:
        return next((w for w in self.warriors if w.id == wid), None)


@dataclass
class Actions:
    train_n: int = 0
    moves: list[tuple[WarriorId, int]] = field(default_factory=list)
    upgrades: list[int] = field(default_factory=list)


def make_base(region: int, s: Side) -> Building:
    return Building(region, s, BType.BASE, 1, BASE_LEVELS[1].hp)


def readln() -> str:
    line = sys.stdin.readline()
    if not line:
        sys.exit(0)
    return line.rstrip("\n")


def read_tokens() -> list[str]:
    return readln().split()


def parse_init() -> tuple[GameMap, GameState]:
    M = GameMap()

    t = read_tokens()
    assert len(t) >= 2 and t[0] == "READY"
    M.my_side = Side.from_word(t[1])

    t = read_tokens()
    M.N, M.K = int(t[0]), int(t[1])

    M.x = [int(v) for v in read_tokens()]  # x_0 x_1 ... x_{N-1}
    M.y = [int(v) for v in read_tokens()]  # y_0 y_1 ... y_{N-1}

    M.strongholds = sorted(int(v) for v in read_tokens())  # K strongholds

    M.adj = [[] for _ in range(M.N)]
    for r in range(M.N):
        t = read_tokens()  # deg n_1 n_2 ...
        deg = int(t[0])
        M.adj[r] = sorted(int(v) for v in t[1:1 + deg])

    M.my_hq = M.hq_of(M.my_side)
    M.opp_hq = M.hq_of(M.my_side.opposite)

    S = GameState()
    opp = M.my_side.opposite
    for sfx in range(1, START_WARRIORS + 1):
        S.warriors.append(Warrior(WarriorId(M.my_side, sfx), M.my_hq, HQ_LEVELS[1].warrior_hp))
        S.warriors.append(Warrior(WarriorId(opp, sfx), M.opp_hq, HQ_LEVELS[1].warrior_hp))
    S.buildings.append(
        Building(0, Side.LEFT, BType.HQ, 1, HQ_LEVELS[1].hp)
    )
    S.buildings.append(
        Building(M.N - 1, Side.RIGHT, BType.HQ, 1, HQ_LEVELS[1].hp)
    )

    print("OK", flush=True)
    return M, S


def read_turn_start() -> int | None:
    line = readln()
    if line == "FINISH":
        return None
    t = line.split()
    assert t and t[0] == "START"
    return int(t[2])


def read_turn_result(S: GameState, M: GameMap, submitted: Actions) -> None:
    for region in submitted.upgrades:
        b = S.find_building(region)
        if b is None:
            S.gold -= BASE_LEVELS[1].cost
            S.buildings.append(make_base(region, M.my_side))
        else:
            max_level = HQ_MAX_LEVEL if b.type is BType.HQ else BASE_MAX_LEVEL
            if b.level >= max_level:
                cost = HQ_HEAL_COST if b.type is BType.HQ else BASE_HEAL_COST
                S.gold -= cost
                b.hp = b.current_hp()
            else:
                S.gold -= b.upgrade_cost()
                b.apply_upgrade()

    for wid, target in submitted.moves:
        b = S.find_building(target)
        cost = 0 if (b is not None and b.side is M.my_side) else MOVE_COST
        S.gold -= cost
        w = S.find_warrior(wid)
        if w is not None:
            w.state = WState.MOVING
            w.target = target

    S.gold -= TRAIN_COST * submitted.train_n

    line = readln()
    if line == "FINISH":
        sys.exit(0)
    t = line.split()
    assert t and t[0] == "TURN"

    t = read_tokens()
    S.my_countdown = int(t[2])
    S.opp_countdown = int(t[4])

    # UPGRADE
    t = read_tokens()  # "UPGRADE N"
    n = int(t[1])
    for _ in range(n):
        r = read_tokens()  # "<A|B> <region>"
        s = Side.from_char(r[0][0])
        region = int(r[1])
        b = S.find_building(region)
        if b is None:
            S.buildings.append(make_base(region, s))
        elif b.side is not M.my_side:
            max_level = HQ_MAX_LEVEL if b.type is BType.HQ else BASE_MAX_LEVEL
            if b.level >= max_level:
                b.hp = b.current_hp()
            else:
                b.apply_upgrade()

    # TRAIN
    t = read_tokens()  # "TRAIN N"
    n = int(t[1])
    if n > 0:
        ids = read_tokens()
        for i in range(n):
            wid = WarriorId.parse(ids[i])
            hq_region = M.hq_of(wid.side)
            hq_b = S.find_building(hq_region)
            hq_level = hq_b.level if hq_b is not None else 1
            S.warriors.append(Warrior(wid, hq_region, HQ_LEVELS[hq_level].warrior_hp))

    # MOVE
    t = read_tokens()  # "MOVE N"
    n = int(t[1])
    for _ in range(n):
        r = read_tokens()
        wid = WarriorId.parse(r[0])
        region = int(r[1])
        w = S.find_warrior(wid)
        if w is not None:
            w.region = region
            if (wid.side is M.my_side
                    and w.state is WState.MOVING
                    and w.region == w.target):
                w.state = WState.STATIONARY

    # DAMAGE
    t = read_tokens()  # "DAMAGE N"
    n = int(t[1])
    for _ in range(n):
        r = read_tokens()
        wid = WarriorId.parse(r[1])
        damage = int(r[2])
        w = S.find_warrior(wid)
        if w is not None:
            w.hp -= damage
    S.warriors = [w for w in S.warriors if w.hp > 0]

    # SIEGE
    t = read_tokens()  # "SIEGE N"
    n = int(t[1])
    for _ in range(n):
        r = read_tokens()
        region = int(r[1])
        dmg = int(r[2])
        b = S.find_building(region)
        if b is not None:
            b.hp -= dmg
    S.buildings = [b for b in S.buildings if b.hp > 0]

    readln()  # "END"

    income = 0
    for b in S.buildings:
        if b.side is not M.my_side:
            continue
        count = sum(
            1 for w in S.warriors
            if w.id.side is M.my_side and w.region == b.region
        )
        income += WORK_INCOME * min(count, b.work_cap())
    S.gold += income

    alive = sum(1 for w in S.warriors if w.id.side is M.my_side)
    S.gold = max(0, S.gold - UPKEEP_PER_WARRIOR * alive)


@dataclass
class Paths:
    dist: list[list[float]]
    nxt: list[list[int]]
    hop_dist: list[list[int]]


def euclid_ceil(M: GameMap, u: int, v: int) -> float:
    return math.ceil(math.hypot(M.x[u] - M.x[v], M.y[u] - M.y[v]))


def calculate_paths(M: GameMap) -> Paths:
    INF = math.inf
    N = M.N
    HOP_INF = N  # hop 수의 최대값은 N-1을 넘지 않으므로 N으로 설정
    dist = [[INF] * N for _ in range(N)]
    nxt = [[-1] * N for _ in range(N)]
    hop_dist = [[HOP_INF] * N for _ in range(N)]

    for i in range(N):
        dist[i][i] = 0.0
        nxt[i][i] = i
        hop_dist[i][i] = 0
    for u in range(N):
        for v in M.adj[u]:
            w = euclid_ceil(M, u, v)
            if w < dist[u][v]:
                dist[u][v] = w
                hop_dist[u][v] = 1  # 인접 노드는 hop 수 1

    # Floyd-Warshall
    for k in range(N):
        dk = dist[k]
        hk = hop_dist[k]
        for u in range(N):
            du = dist[u]
            hu = hop_dist[u]
            duk = du[k]
            huk = hu[k]
            if duk == INF:
                continue
            for v in range(N):
                cand_dist = duk + dk[v]
                if cand_dist < du[v]:
                    du[v] = cand_dist
                    hu[v] = huk + hk[v]

    for u in range(N):
        du = dist[u]
        for v in range(N):
            if u == v or du[v] == INF:
                continue
            best_score = INF
            for nb in M.adj[u]:
                if dist[nb][v] == INF:
                    continue
                score = euclid_ceil(M, u, nb) + dist[nb][v]
                if score < best_score:
                    best_score = score
                    nxt[u][v] = nb
    return Paths(dist, nxt, hop_dist)


def next_step(P: Paths, u: int, v: int) -> int:
    """Returns the next step on the path from u to v. Returns -1 if the path is not reachable."""
    return P.nxt[u][v]


def path(P: Paths, u: int, v: int) -> list[int]:
    """Returns the path from u to v as [u, ..., v]. Returns an empty list if the path is not reachable."""
    if P.nxt[u][v] == -1:
        return []
    out = [u]
    while u != v:
        u = P.nxt[u][v]
        out.append(u)
    return out


def emit(a: Actions) -> None:
    out: list[str] = ["COMMAND"]
    for wid, target in a.moves:
        out.append(f"MOVE {wid} {target}")
    for r in a.upgrades:
        out.append(f"UPGRADE {r}")
    if a.train_n > 0:
        out.append(f"TRAIN {a.train_n}")
    out.append("END")
    sys.stdout.write("\n".join(out) + "\n")
    sys.stdout.flush()


def log_decision(turn: int, data: dict[str, Any]) -> None:
    """Log decision data to stderr in JSON format."""
    data["turn"] = turn
    print(json.dumps(data), file=sys.stderr)
    sys.stderr.flush()


def calculate_income(S: GameState, M: GameMap) -> int:
    income = 0
    for b in S.buildings:
        if b.side is not M.my_side:
            continue
        count = sum(1 for w in S.warriors if w.id.side is M.my_side and w.region == b.region)
        income += WORK_INCOME * min(count, b.work_cap())
    return income


def calculate_upkeep(S: GameState, M: GameMap) -> int:
    return UPKEEP_PER_WARRIOR * sum(1 for w in S.warriors if w.id.side is M.my_side)


def calculate_worker_cap(S: GameState, M: GameMap) -> int:
    return sum(b.work_cap() for b in S.buildings if b.side is M.my_side)


def get_building_turret(b: Building) -> int:
    if b.type is BType.HQ:
        return HQ_LEVELS[b.level].turret
    else:
        return BASE_LEVELS[b.level].turret


def simulate_combat(S: GameState, M: GameMap) -> None:
    """Simulate combat phase (Day phase) and update state."""
    # Group warriors by region
    region_warriors: dict[int, list[Warrior]] = {}
    for w in S.warriors:
        if w.region not in region_warriors:
            region_warriors[w.region] = []
        region_warriors[w.region].append(w)

    # Process each region independently
    for region, warriors in region_warriors.items():
        # Split warriors by side
        my_warriors = [w for w in warriors if w.id.side is M.my_side]
        opp_warriors = [w for w in warriors if w.id.side is M.my_side.opposite]

        # Get buildings in this region
        my_building = S.find_building(region) if (S.find_building(region) and S.find_building(region).side is M.my_side) else None
        opp_building = S.find_building(region) if (S.find_building(region) and S.find_building(region).side is M.my_side.opposite) else None

        # Apply turret attacks first
        # My turret attacks enemy warriors
        if my_building:
            turret_dmg = get_building_turret(my_building)
            for _ in range(turret_dmg):
                if not opp_warriors:
                    break
                # Find enemy warrior with lowest HP, smallest ID
                target = min(opp_warriors, key=lambda w: (w.hp, str(w.id)))
                target.hp -= 1

        # Opponent turret attacks my warriors
        if opp_building:
            turret_dmg = get_building_turret(opp_building)
            for _ in range(turret_dmg):
                if not my_warriors:
                    break
                target = min(my_warriors, key=lambda w: (w.hp, str(w.id)))
                target.hp -= 1

        # Now warrior attacks
        # My warriors attack
        for w in list(my_warriors):  # list() because we might modify during iteration
            if opp_warriors:
                target = min(opp_warriors, key=lambda ww: (ww.hp, str(ww.id)))
                target.hp -= 1
            elif opp_building:
                opp_building.hp -= 1
        # Opp warriors attack
        for w in list(opp_warriors):
            if my_warriors:
                target = min(my_warriors, key=lambda ww: (ww.hp, str(ww.id)))
                target.hp -= 1
            elif my_building:
                my_building.hp -= 1

    # Now remove dead warriors and buildings
    S.warriors = [w for w in S.warriors if w.hp > 0]
    S.buildings = [b for b in S.buildings if b.hp > 0]


def simulate_evening(S: GameState, M: GameMap) -> None:
    """Simulate evening phase (income and upkeep)."""
    income = calculate_income(S, M)
    upkeep = calculate_upkeep(S, M)
    S.gold += income
    S.gold = max(0, S.gold - upkeep)


def deep_copy_state(S: GameState) -> GameState:
    """Create a deep copy of GameState for simulation."""
    warriors = [Warrior(WarriorId(w.id.side, w.id.num), w.region, w.hp, w.state, w.target) for w in S.warriors]
    buildings = [Building(b.region, b.side, b.type, b.level, b.hp) for b in S.buildings]
    return GameState(S.gold, S.my_countdown, S.opp_countdown, warriors, buildings)


def evaluate_state(S: GameState, M: GameMap, P: Paths, turn: int) -> float:
    """Static evaluation function for GameState (higher is better)."""
    score = 0.0

    # Get our HQ and enemy HQ
    my_hq = S.find_building(M.my_hq)
    opp_hq = S.find_building(M.opp_hq)

    # --- 1. HQ Health ---
    my_hq_hp = my_hq.hp if my_hq else 0
    opp_hq_hp = opp_hq.hp if opp_hq else 0
    if my_hq_hp <= 0:
        return -100000.0  # Losing condition
    if opp_hq_hp <= 0:
        return 100000.0  # Winning condition
    score += (my_hq_hp - opp_hq_hp) * 100.0

    # --- 2. Army Value ---
    my_army_val = sum(w.hp for w in S.warriors if w.id.side is M.my_side)
    opp_army_val = sum(w.hp for w in S.warriors if w.id.side is M.my_side.opposite)
    score += (my_army_val - opp_army_val) * 10.0

    # --- 3. Economic Health ---
    worker_cap = calculate_worker_cap(S, M)
    army_size = sum(1 for w in S.warriors if w.id.side is M.my_side)
    if army_size > 7.5 * worker_cap:
        score -= 500.0  # Penalty for over-saturating army (starvation risk)
    income = calculate_income(S, M)
    upkeep = calculate_upkeep(S, M)
    score += (income - upkeep) * 2.0
    score += S.gold * 0.1

    # --- 4. Base Control ---
    my_bases = sum(1 for b in S.buildings if b.side is M.my_side and b.type is BType.BASE)
    opp_bases = sum(1 for b in S.buildings if b.side is M.my_side.opposite and b.type is BType.BASE)
    score += (my_bases - opp_bases) * 200.0

    # --- 5. Tempo / Proximity ---
    my_prox = 0.0
    opp_prox = 0.0
    for w in S.warriors:
        if w.id.side is M.my_side:
            d = P.dist[w.region][M.opp_hq] if P.dist[w.region][M.opp_hq] < math.inf else 100.0
            my_prox += w.hp / (d + 1.0)
        else:
            d = P.dist[w.region][M.my_hq] if P.dist[w.region][M.my_hq] < math.inf else 100.0
            opp_prox += w.hp / (d + 1.0)
    score += (my_prox - opp_prox) * 5.0

    # --- 6. Time Decay for Economic Investments ---
    time_left = MAX_TURN - turn
    for b in S.buildings:
        if b.side is M.my_side and b.type is BType.BASE:
            base_value = 200.0 * (time_left / MAX_TURN)
            score += base_value

    return score


def generate_candidates(S: GameState, M: GameMap, P: Paths, turn: int) -> list[Actions]:
    """Generate candidate macro-action plans."""
    candidates: list[Actions] = []

    # Candidate 0: Do nothing (save gold)
    candidates.append(Actions())

    # Get our stationary warriors
    my_stationary = [w for w in S.warriors if w.id.side is M.my_side and w.state is WState.STATIONARY]
    my_hq_b = S.find_building(M.my_hq)
    train_cap = HQ_LEVELS[my_hq_b.level].train_cap if my_hq_b else 0

    # Candidate 1: All-in attack (move all to enemy HQ)
    a1 = Actions()
    for w in my_stationary:
        a1.moves.append((w.id, M.opp_hq))
    candidates.append(a1)

    # Candidate 2: Expand to nearest stronghold if possible
    if turn < 175:  # Don't build bases too late
        nearest_sh = None
        min_dist = math.inf
        for sh in M.strongholds:
            if S.find_building(sh):
                continue  # Already has a base
            # Check if any of our warriors can reach it
            for w in my_stationary:
                d = P.dist[w.region][sh] if P.dist[w.region][sh] < math.inf else 1000.0
                if d < min_dist:
                    min_dist = d
                    nearest_sh = sh
        if nearest_sh is not None and S.gold >= BASE_LEVELS[1].cost:
            a2 = Actions()
            # Move a warrior there (if not already there)
            warrior_for_sh = None
            for w in my_stationary:
                if warrior_for_sh is None or P.dist[w.region][nearest_sh] < P.dist[warrior_for_sh.region][nearest_sh]:
                    warrior_for_sh = w
            if warrior_for_sh:
                a2.moves.append((warrior_for_sh.id, nearest_sh))
            # Try to upgrade (build base) there
            a2.upgrades.append(nearest_sh)
            candidates.append(a2)

    # Candidate 3: Train warriors if possible
    if S.gold >= TRAIN_COST * 1 and train_cap >= 1:
        a3 = Actions()
        a3.train_n = min(train_cap, S.gold // TRAIN_COST)
        candidates.append(a3)

    return candidates


# from evaluation_function import EvaluationFunction, Weights
# from action_selector import ActionSelector


def decide(S: GameState, M: GameMap, P: Paths, turn: int) -> Actions:
    """Strategy: use evaluation function to pick the best candidate actions."""
    weights = Weights()
    eval_fn = EvaluationFunction(weights)
    selector = ActionSelector(eval_fn)

    # Log initial state
    initial_data = {
        "gold": S.gold,
        "income": calculate_income(S, M),
        "upkeep": calculate_upkeep(S, M),
    }

    # Select best actions
    best_actions = selector.select_best_actions(S, M, P, turn)

    # Log decision
    log_decision(turn, {
        **initial_data,
        "chosen_train": best_actions.train_n,
        "chosen_moves": len(best_actions.moves),
        "chosen_upgrades": len(best_actions.upgrades)
    })

    return best_actions


def main() -> None:
    M, S = parse_init()
    P = calculate_paths(M)

    while (turn := read_turn_start()) is not None:
        a = decide(S, M, P, turn)
        emit(a)
        read_turn_result(S, M, a)


if __name__ == "__main__":
    main()
# --- END main.py ---
