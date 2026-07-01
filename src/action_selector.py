
"""
Action Selector Module for NYPC 2026 AI
Selects the best candidate actions based on scores
"""
from __future__ import annotations
import math
import sys
import json
from main import GameState, GameMap, Paths, Actions
from candidate_generator import CandidateGenerator
from evaluation_function import EvaluationFunction


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
        from main import MOVE_COST, TRAIN_COST, BASE_LEVELS, HQ_LEVELS, BType
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
