
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
        from main import START_GOLD

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
        from main import START_GOLD

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
        from main import START_GOLD

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
