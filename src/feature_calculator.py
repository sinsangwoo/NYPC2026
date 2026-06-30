
"""
Feature Calculator Module for NYPC 2026 AI
Calculates all required features for Evaluation Function
"""
from __future__ import annotations
import math
from dataclasses import dataclass
from typing import NamedTuple
from main import (
    GameState, GameMap, Paths, WarriorId, Warrior,
    MOVE_COST, TRAIN_COST, BASE_LEVELS, HQ_LEVELS, BType
)


@dataclass
class MoveFeatures:
    dist_to_enemy_hq: float
    dist_to_nearest_enemy: float
    adj_allies_count: int
    adj_enemies_count: int
    is_stronghold: bool
    is_hq_adjacent: bool
    is_on_hq: bool
    move_cost: int
    turns_remaining: int
    remaining_gold_after_action: int


@dataclass
class TrainFeatures:
    train_n: int
    train_cost: int
    turns_remaining: int
    remaining_gold_after_action: int


@dataclass
class UpgradeFeatures:
    region: int
    upgrade_cost: int
    is_stronghold: bool
    turns_remaining: int
    remaining_gold_after_action: int


class FeatureCalculator:
    @staticmethod
    def calculate_move_features(
        S: GameState, M: GameMap, P: Paths,
        warrior: Warrior, target_region: int, turn: int
    ) -> MoveFeatures:
        """Calculate features for a MOVE action."""
        # Distance to enemy HQ
        dist_to_enemy_hq = P.dist[target_region][M.opp_hq]
        if math.isinf(dist_to_enemy_hq):
            dist_to_enemy_hq = 1000.0

        # Distance to nearest enemy
        dist_to_nearest_enemy = math.inf
        for w in S.warriors:
            if w.id.side != M.my_side:
                d = P.dist[target_region][w.region]
                if not math.isinf(d) and d < dist_to_nearest_enemy:
                    dist_to_nearest_enemy = d
        if math.isinf(dist_to_nearest_enemy):
            dist_to_nearest_enemy = 1000.0

        # Adjacent allies and enemies
        adj_allies_count = 0
        adj_enemies_count = 0
        for w in S.warriors:
            if w.region == target_region:
                if w.id.side == M.my_side:
                    adj_allies_count += 1
                else:
                    adj_enemies_count += 1
        # Also count allies moving to same target? Maybe later, let's keep simple now.

        # Stronghold, HQ checks
        is_stronghold = target_region in M.strongholds
        is_hq_adjacent = target_region in M.adj[M.opp_hq]
        is_on_hq = target_region == M.opp_hq

        # Move cost
        target_building = S.find_building(target_region)
        move_cost = 0 if (target_building and target_building.side == M.my_side) else MOVE_COST

        # Remaining turns
        turns_remaining = 200 - turn

        # Remaining gold after action
        remaining_gold_after_action = S.gold - move_cost

        return MoveFeatures(
            dist_to_enemy_hq=dist_to_enemy_hq,
            dist_to_nearest_enemy=dist_to_nearest_enemy,
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
        train_cost = TRAIN_COST * train_n
        turns_remaining = 200 - turn
        remaining_gold_after_action = S.gold - train_cost

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
            upgrade_cost = BASE_LEVELS[1].cost
        elif target_building.type == BType.HQ:
            max_level = len(HQ_LEVELS) - 1
            if target_building.level < max_level:
                upgrade_cost = target_building.upgrade_cost()
            else:
                upgrade_cost = 1000  # HQ heal cost
        else:
            max_level = len(BASE_LEVELS) - 1
            if target_building.level < max_level:
                upgrade_cost = target_building.upgrade_cost()
            else:
                upgrade_cost = 500  # Base heal cost

        is_stronghold = region in M.strongholds
        turns_remaining = 200 - turn
        remaining_gold_after_action = S.gold - upgrade_cost

        return UpgradeFeatures(
            region=region,
            upgrade_cost=upgrade_cost,
            is_stronghold=is_stronghold,
            turns_remaining=turns_remaining,
            remaining_gold_after_action=remaining_gold_after_action
        )
