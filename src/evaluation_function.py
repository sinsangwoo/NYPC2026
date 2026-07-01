
"""
Evaluation Function Module for NYPC 2026 AI
Calculates scores for candidate actions using features
"""
from __future__ import annotations
import math
import sys
import json
from dataclasses import dataclass
from main import GameState, GameMap, Paths, Actions, Warrior, WState
from feature_calculator import FeatureCalculator, MoveFeatures, TrainFeatures, UpgradeFeatures


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
