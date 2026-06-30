
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
    w_dist_to_enemy_hq: float = -10.0
    w_dist_to_nearest_enemy: float = -5.0
    w_adj_allies_count: float = 2.0
    w_adj_enemies_count: float = -10.0
    w_is_stronghold: float = 1.0
    w_is_on_hq: float = 1000.0
    w_is_hq_adjacent: float = 500.0
    w_move_cost: float = -0.0
    w_turns_remaining: float = 0.0
    w_remaining_gold_after_action: float = 0.1

    # Train weights
    w_train_n: float = 50.0
    w_train_cost: float = -0.01
    w_train_remaining_gold: float = 0.1
    w_train_turns_remaining: float = 0.0

    # Upgrade weights
    w_upgrade_is_stronghold: float = 200.0
    w_upgrade_cost: float = -0.01
    w_upgrade_remaining_gold: float = 0.1
    w_upgrade_turns_remaining: float = 0.0


class EvaluationFunction:
    def __init__(self, weights: Weights = Weights()):
        self.weights = weights

    def evaluate_move(self, features: MoveFeatures) -> float:
        score = 0.0
        components = []

        components.append(("w_dist_to_enemy_hq", self.weights.w_dist_to_enemy_hq, features.dist_to_enemy_hq, self.weights.w_dist_to_enemy_hq * features.dist_to_enemy_hq))
        score += self.weights.w_dist_to_enemy_hq * features.dist_to_enemy_hq

        components.append(("w_dist_to_nearest_enemy", self.weights.w_dist_to_nearest_enemy, features.dist_to_nearest_enemy, self.weights.w_dist_to_nearest_enemy * features.dist_to_nearest_enemy))
        score += self.weights.w_dist_to_nearest_enemy * features.dist_to_nearest_enemy

        components.append(("w_adj_allies_count", self.weights.w_adj_allies_count, features.adj_allies_count, self.weights.w_adj_allies_count * features.adj_allies_count))
        score += self.weights.w_adj_allies_count * features.adj_allies_count

        components.append(("w_adj_enemies_count", self.weights.w_adj_enemies_count, features.adj_enemies_count, self.weights.w_adj_enemies_count * features.adj_enemies_count))
        score += self.weights.w_adj_enemies_count * features.adj_enemies_count

        components.append(("w_is_stronghold", self.weights.w_is_stronghold, 1 if features.is_stronghold else 0, self.weights.w_is_stronghold * (1 if features.is_stronghold else 0)))
        score += self.weights.w_is_stronghold * (1 if features.is_stronghold else 0)

        components.append(("w_is_on_hq", self.weights.w_is_on_hq, 1 if features.is_on_hq else 0, self.weights.w_is_on_hq * (1 if features.is_on_hq else 0)))
        score += self.weights.w_is_on_hq * (1 if features.is_on_hq else 0)

        components.append(("w_is_hq_adjacent", self.weights.w_is_hq_adjacent, 1 if features.is_hq_adjacent else 0, self.weights.w_is_hq_adjacent * (1 if features.is_hq_adjacent else 0)))
        score += self.weights.w_is_hq_adjacent * (1 if features.is_hq_adjacent else 0)

        components.append(("w_move_cost", self.weights.w_move_cost, features.move_cost, self.weights.w_move_cost * features.move_cost))
        score += self.weights.w_move_cost * features.move_cost

        components.append(("w_turns_remaining", self.weights.w_turns_remaining, features.turns_remaining, self.weights.w_turns_remaining * features.turns_remaining))
        score += self.weights.w_turns_remaining * features.turns_remaining

        components.append(("w_remaining_gold_after_action", self.weights.w_remaining_gold_after_action, features.remaining_gold_after_action, self.weights.w_remaining_gold_after_action * features.remaining_gold_after_action))
        score += self.weights.w_remaining_gold_after_action * features.remaining_gold_after_action

        # Debug: Print move evaluation
        debug_data = {
            "type": "move",
            "features": {
                "dist_to_enemy_hq": features.dist_to_enemy_hq,
                "dist_to_nearest_enemy": features.dist_to_nearest_enemy,
                "adj_allies_count": features.adj_allies_count,
                "adj_enemies_count": features.adj_enemies_count,
                "is_stronghold": features.is_stronghold,
                "is_on_hq": features.is_on_hq,
                "is_hq_adjacent": features.is_hq_adjacent,
                "move_cost": features.move_cost,
                "turns_remaining": features.turns_remaining,
                "remaining_gold_after_action": features.remaining_gold_after_action
            },
            "components": components,
            "total_score": score
        }
        print(json.dumps(debug_data), file=sys.stderr)
        sys.stderr.flush()

        return score

    def evaluate_train(self, features: TrainFeatures) -> float:
        score = 0.0
        components = []

        components.append(("w_train_n", self.weights.w_train_n, features.train_n, self.weights.w_train_n * features.train_n))
        score += self.weights.w_train_n * features.train_n

        components.append(("w_train_cost", self.weights.w_train_cost, features.train_cost, self.weights.w_train_cost * features.train_cost))
        score += self.weights.w_train_cost * features.train_cost

        components.append(("w_train_remaining_gold", self.weights.w_train_remaining_gold, features.remaining_gold_after_action, self.weights.w_train_remaining_gold * features.remaining_gold_after_action))
        score += self.weights.w_train_remaining_gold * features.remaining_gold_after_action

        components.append(("w_train_turns_remaining", self.weights.w_train_turns_remaining, features.turns_remaining, self.weights.w_train_turns_remaining * features.turns_remaining))
        score += self.weights.w_train_turns_remaining * features.turns_remaining

        # Debug: Print train evaluation
        debug_data = {
            "type": "train",
            "features": {
                "train_n": features.train_n,
                "train_cost": features.train_cost,
                "remaining_gold_after_action": features.remaining_gold_after_action,
                "turns_remaining": features.turns_remaining
            },
            "components": components,
            "total_score": score
        }
        print(json.dumps(debug_data), file=sys.stderr)
        sys.stderr.flush()

        return score

    def evaluate_upgrade(self, features: UpgradeFeatures) -> float:
        score = 0.0
        components = []

        components.append(("w_upgrade_is_stronghold", self.weights.w_upgrade_is_stronghold, 1 if features.is_stronghold else 0, self.weights.w_upgrade_is_stronghold * (1 if features.is_stronghold else 0)))
        score += self.weights.w_upgrade_is_stronghold * (1 if features.is_stronghold else 0)

        components.append(("w_upgrade_cost", self.weights.w_upgrade_cost, features.upgrade_cost, self.weights.w_upgrade_cost * features.upgrade_cost))
        score += self.weights.w_upgrade_cost * features.upgrade_cost

        components.append(("w_upgrade_remaining_gold", self.weights.w_upgrade_remaining_gold, features.remaining_gold_after_action, self.weights.w_upgrade_remaining_gold * features.remaining_gold_after_action))
        score += self.weights.w_upgrade_remaining_gold * features.remaining_gold_after_action

        components.append(("w_upgrade_turns_remaining", self.weights.w_upgrade_turns_remaining, features.turns_remaining, self.weights.w_upgrade_turns_remaining * features.turns_remaining))
        score += self.weights.w_upgrade_turns_remaining * features.turns_remaining

        # Debug: Print upgrade evaluation
        debug_data = {
            "type": "upgrade",
            "features": {
                "is_stronghold": features.is_stronghold,
                "upgrade_cost": features.upgrade_cost,
                "remaining_gold_after_action": features.remaining_gold_after_action,
                "turns_remaining": features.turns_remaining
            },
            "components": components,
            "total_score": score
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
