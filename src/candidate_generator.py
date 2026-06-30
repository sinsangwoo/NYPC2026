
"""
Candidate Action Generator Module for NYPC 2026 AI
Generates possible candidate actions for the AI
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Union, NamedTuple
from main import (
    GameState, GameMap, Paths, WarriorId, Warrior,
    Actions, TRAIN_COST, BASE_LEVELS, HQ_LEVELS, HQ_MAX_LEVEL, BASE_MAX_LEVEL,
    WState, MOVE_COST, BType
)


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
