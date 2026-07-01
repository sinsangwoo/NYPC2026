#!/usr/bin/env python3
"""
NYPC 2026 STEP 6A - Behavior Benchmark
각 Weight Sweep 결과 로그에 대해 다음 메트릭을 자동 수집:
  - Movement (MOVE 선택율, 첫 MOVE Turn, 평균 이동 거리, HQ 접근량)
  - Stronghold (방문 횟수, 첫 방문 Turn, 점유 Turn)
  - Upgrade (후보 생성 횟수, 선택 횟수, 첫 Upgrade Turn)
  - Training (선택 횟수, 평균 train_n)
  - HQ (평균 거리, 최소 거리, 인접 도달, 공격)

+ 기존 Feature/Contribution/Final Score Distribution
+ Behavior Distribution (MOVE/TRAIN/UPGRADE/WAIT 선택 비율)

사용 예:
  python scripts/behavior_benchmark.py
"""

import os
import sys
import json
import statistics
import re
from pathlib import Path
from collections import defaultdict, Counter
from datetime import datetime


########################################
# Experiment Configuration
########################################

# 분석 대상 디렉토리
PROJECT_ROOT = Path(__file__).parent.parent
SWEEP_BASE_DIR = PROJECT_ROOT / "logs" / "weight_sweep_step6e"
REPORT_DIR = PROJECT_ROOT / "logs" / "weight_sweep_step6e" / "report"

# 분석할 Side
ANALYZE_SIDES = ["LEFT", "RIGHT"]

# 출력 파일
BEHAVIOR_SUMMARY_CSV = REPORT_DIR / "behavior_summary.csv"
BEHAVIOR_SUMMARY_JSON = REPORT_DIR / "behavior_summary.json"
DISTRIBUTION_REPORT = REPORT_DIR / "distributions.json"
########################################


# =============================================================================
# 1. Log Parser
# =============================================================================

def parse_map(lines):
    """로그 시작의 MAP 블록 파싱"""
    map_data = {
        "N": 0, "K": 0,
        "x": [], "y": [],
        "strongholds": [],
        "adj": []
    }
    idx = 0
    # "MAP" 라인 찾기
    while idx < len(lines) and lines[idx].strip() != "MAP":
        idx += 1
    if idx >= len(lines):
        return None, -1
    idx += 1

    # N K
    parts = lines[idx].split()
    map_data["N"] = int(parts[0])
    map_data["K"] = int(parts[1])
    idx += 1

    # x 좌표
    map_data["x"] = list(map(int, lines[idx].split()))
    idx += 1
    # y 좌표
    map_data["y"] = list(map(int, lines[idx].split()))
    idx += 1

    # STRONGHOLDS (있으면)
    if idx < len(lines) and lines[idx].startswith("STRONGHOLDS"):
        map_data["strongholds"] = list(map(int, lines[idx].split()[1:]))
        idx += 1

    # 인접 리스트
    map_data["adj"] = []
    for _ in range(map_data["N"]):
        if idx >= len(lines):
            break
        parts = lines[idx].split()
        deg = int(parts[0])
        adj = sorted(int(v) for v in parts[1:1 + deg])
        map_data["adj"].append(adj)
        idx += 1

    # END MAP
    if idx < len(lines) and lines[idx].strip() == "END MAP":
        idx += 1

    return map_data, idx


def parse_log(log_path):
    """단일 로그 파싱 - 모든 이벤트 추출"""
    with open(log_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    map_data, map_end_idx = parse_map(lines)
    if map_data is None:
        return None

    # side별 파싱
    side_data = {
        side: {
            "warrior_positions": {},      # {warrior_id: region}
            "warrior_history": [],       # (turn, warrior_id, new_region)
            "move_distances": [],        # (turn, hop_dist)
            "candidate_upgrades": [],    # (turn, upgrade_count_in_candidates)
            "candidate_scores": [],      # turn 별 top1, top2 score (candidates 분석)
            "chosen_actions": [],        # (turn, train, moves, upgrades)
            "upgrades_executed": [],     # (turn, region) - 실제 UPGRADE 명령
            "first_move_turn": None,
            "first_stronghold_visit": None,
            "first_upgrade_turn": None,
            "stronghold_visits": 0,      # turn count where warrior on stronghold
            "hq_distances_per_turn": [], # (turn, min_hop_dist_to_opp_hq)
            "unique_regions_visited": set(),  # warrior가 방문한 unique region 집합
            # [NEW] Gold 시계열
            "gold_time_series": [],      # (turn, gold, income, upkeep)
            # [NEW] Action Rank Distribution - 선택된 행동의 순위
            "chosen_action_ranks": [],   # (turn, rank_of_chosen)
            # [NEW] Contribution per weight
            "contributions_per_turn": []  # (turn, {weight_name: contrib_value})
        }
        for side in ANALYZE_SIDES
    }

    # opp_hq
    # LEFT: 0, RIGHT: N-1
    opp_hq_map = {"LEFT": map_data["N"] - 1, "RIGHT": 0}

    # 초기 warrior 위치 (각 side HQ)
    initial_warrior_ids = {
        "LEFT": ["A1", "A2", "A3"],
        "RIGHT": ["B1", "B2", "B3"]
    }
    for side, ids in initial_warrior_ids.items():
        for wid in ids:
            # 자기 HQ: LEFT=0, RIGHT=N-1
            if side == "LEFT":
                side_data[side]["warrior_positions"][wid] = 0
            else:
                side_data[side]["warrior_positions"][wid] = map_data["N"] - 1
            # 초기 HQ region도 unique에 포함
            side_data[side]["unique_regions_visited"].add(side_data[side]["warrior_positions"][wid])

    current_turn = 0

    for i in range(map_end_idx, len(lines)):
        line = lines[i].rstrip("\n")

        # TURN N (RESULT 아님)
        if line.startswith("TURN ") and not line.startswith("TURN 1 RESULT"):
            try:
                t_parts = line.split()
                if t_parts[0] == "TURN" and t_parts[1].isdigit():
                    current_turn = int(t_parts[1])
            except (ValueError, IndexError):
                pass

        # Debug 라인 (stderr) - LEFT/RIGHT 모두 파싱
        for side in ANALYZE_SIDES:
            debug_prefix = f"# Debug {side}:"
            if line.startswith(debug_prefix):
                try:
                    json_str = line[len(debug_prefix):].strip()
                    debug_obj = json.loads(json_str)

                    # [NEW] Gold 시계열 수집
                    if "gold" in debug_obj and "income" in debug_obj and "upkeep" in debug_obj:
                        turn = debug_obj.get("turn", current_turn)
                        side_data[side]["gold_time_series"].append((
                            turn,
                            debug_obj.get("gold", 0),
                            debug_obj.get("income", 0),
                            debug_obj.get("upkeep", 0)
                        ))

                    # candidates: upgrade 후보 + score 통계
                    if "candidates" in debug_obj and "turn" in debug_obj:
                        turn = debug_obj["turn"]
                        candidates = debug_obj["candidates"]
                        upgrade_count = sum(1 for c in candidates if c.get("upgrades"))
                        side_data[side]["candidate_upgrades"].append((turn, upgrade_count))

                        # Score 통계: affordable candidates의 score 추출
                        scores = sorted(
                            [c["score"] for c in candidates if c.get("affordable", False)],
                            reverse=True
                        )
                        if scores:
                            top1 = scores[0]
                            top2 = scores[1] if len(scores) >= 2 else scores[0]
                            side_data[side]["candidate_scores"].append((turn, top1, top2))

                        # [NEW] Action Rank Distribution - 선택된 행동의 순위
                        if "best_idx" in debug_obj:
                            best_idx = debug_obj["best_idx"]
                            # rank는 0-indexed, +1해서 1-indexed로
                            rank = best_idx + 1
                            total_candidates = len(candidates)
                            side_data[side]["chosen_action_ranks"].append((turn, rank, total_candidates))

                    # [NEW] Contribution per weight 수집
                    if "contribution_dump" in debug_obj and "turn" in debug_obj:
                        turn = debug_obj.get("turn", current_turn)
                        contrib_dump = debug_obj.get("contribution_dump", {})
                        side_data[side]["contributions_per_turn"].append((turn, contrib_dump))

                    # chosen_actions: chosen_train, chosen_moves, chosen_upgrades
                    if "chosen_train" in debug_obj:
                        turn = debug_obj.get("turn", current_turn)
                        side_data[side]["chosen_actions"].append((
                            turn,
                            debug_obj.get("chosen_train", 0),
                            debug_obj.get("chosen_moves", 0),
                            debug_obj.get("chosen_upgrades", 0)
                        ))
                except (json.JSONDecodeError, KeyError, ValueError):
                    pass

        # TURN X RESULT 라인 이후
        if " RESULT" in line and line.startswith("TURN"):
            try:
                t_parts = line.split()
                turn_num = int(t_parts[1])
            except (ValueError, IndexError):
                continue

            # 다음 END TURN 까지 파싱
            j = i + 1
            turn_moves = {"A": [], "B": []}
            turn_upgrades = {"A": [], "B": []}
            while j < len(lines) and not lines[j].startswith("END TURN"):
                l = lines[j].strip()
                if l.startswith("MOVE"):
                    parts = l.split()
                    if len(parts) >= 3:
                        wid = parts[1]
                        region = int(parts[2])
                        if wid.startswith("A"):
                            turn_moves["A"].append((wid, region))
                        elif wid.startswith("B"):
                            turn_moves["B"].append((wid, region))
                elif l.startswith("UPGRADE"):
                    # 첫 줄은 "UPGRADE N" 형식
                    pass
                else:
                    # UPGRADE의 다음 줄: "A 2" 또는 "B 14"
                    if len(l.split()) == 2:
                        parts = l.split()
                        side_char = parts[0]
                        region = int(parts[1])
                        if side_char in ("A", "B"):
                            turn_upgrades[side_char].append(region)
                j += 1

            # side별로 warrior 위치 업데이트 및 메트릭 계산
            for side in ANALYZE_SIDES:
                prefix = "A" if side == "LEFT" else "B"
                opp_hq = opp_hq_map[side]

                # warrior 위치 업데이트
                for wid, new_region in turn_moves[prefix]:
                    if wid in side_data[side]["warrior_positions"]:
                        old_region = side_data[side]["warrior_positions"][wid]
                        side_data[side]["warrior_history"].append((turn_num, wid, new_region))

                        # hop distance 계산
                        hd = hop_distance(map_data["adj"], old_region, new_region)
                        side_data[side]["move_distances"].append((turn_num, hd))

                        # HQ 접근량
                        old_hd_to_opp = hop_distance(map_data["adj"], old_region, opp_hq)
                        new_hd_to_opp = hop_distance(map_data["adj"], new_region, opp_hq)
                        # (이전 거리 - 새 거리) > 0 이면 접근
                        # (실제 move_distances에 접근량도 추가)

                        side_data[side]["warrior_positions"][wid] = new_region
                        side_data[side]["unique_regions_visited"].add(new_region)

                # 첫 MOVE turn
                if turn_moves[prefix] and side_data[side]["first_move_turn"] is None:
                    side_data[side]["first_move_turn"] = turn_num

                # Stronghold 방문
                on_stronghold = any(
                    side_data[side]["warrior_positions"].get(wid) in map_data["strongholds"]
                    for wid in initial_warrior_ids[side]
                )
                if on_stronghold:
                    side_data[side]["stronghold_visits"] += 1
                    if side_data[side]["first_stronghold_visit"] is None:
                        side_data[side]["first_stronghold_visit"] = turn_num

                # HQ 거리 계산
                if side_data[side]["warrior_positions"]:
                    min_hq_d = min(
                        hop_distance(map_data["adj"], pos, opp_hq)
                        for pos in side_data[side]["warrior_positions"].values()
                    )
                    side_data[side]["hq_distances_per_turn"].append((turn_num, min_hq_d))

                # UPGRADE 처리
                for region in turn_upgrades[prefix]:
                    side_data[side]["upgrades_executed"].append((turn_num, region))
                    if side_data[side]["first_upgrade_turn"] is None:
                        side_data[side]["first_upgrade_turn"] = turn_num

            i = j

    # Result 파싱
    result = {"winner": None, "reason": None}
    for line in lines:
        if line.startswith("RESULT "):
            parts = line.strip().split()
            if len(parts) >= 3:
                result["winner"] = parts[1]
                result["reason"] = parts[2]
            break

    return {
        "map_data": map_data,
        "side_data": side_data,
        "result": result
    }


def hop_distance(adj, u, v):
    """BFS로 u에서 v까지의 hop distance 계산"""
    if u == v:
        return 0
    n = len(adj)
    if u < 0 or u >= n or v < 0 or v >= n:
        return 999
    if not adj[u]:
        return 999
    from collections import deque
    dist = [-1] * n
    dist[u] = 0
    q = deque([u])
    while q:
        cur = q.popleft()
        for nb in adj[cur]:
            if dist[nb] == -1:
                dist[nb] = dist[cur] + 1
                if nb == v:
                    return dist[nb]
                q.append(nb)
    return 999  # unreachable


# =============================================================================
# 2. Behavior Metrics Calculator
# =============================================================================

def compute_behavior_metrics(side_data, total_turns, map_data=None):
    """side_data로부터 Behavior 메트릭 계산"""
    sd = side_data

    # ---- Movement ----
    moves_count = len(sd["warrior_history"])
    avg_moves_per_turn = moves_count / max(total_turns, 1)

    # MOVE 선택 비율: chosen_moves > 0인 turn / total_turns
    turn_with_moves = set(t for t, _, _ in sd["warrior_history"])
    move_select_rate = len(turn_with_moves) / max(total_turns, 1)

    first_move_turn = sd["first_move_turn"]

    move_distances = [d for _, d in sd["move_distances"]]
    avg_move_distance = statistics.mean(move_distances) if move_distances else 0.0

    # HQ 접근량: 각 turn마다 warrior의 min distance to opp_hq, 그 차이
    hq_approaches = []
    sorted_hq = sorted(sd["hq_distances_per_turn"], key=lambda x: x[0])
    for i in range(1, len(sorted_hq)):
        prev_turn, prev_d = sorted_hq[i-1]
        cur_turn, cur_d = sorted_hq[i]
        # prev - cur > 0 이면 접근
        hq_approaches.append(prev_d - cur_d)
    avg_hq_approach = statistics.mean(hq_approaches) if hq_approaches else 0.0

    # ---- Stronghold ----
    strongholds_visit_count = sd["stronghold_visits"]
    first_stronghold_visit = sd["first_stronghold_visit"]

    # Stronghold capture: UPGRADE 명령이 stronghold에 대한 것인지
    stronghold_capture_count = 0
    base_construction_count = 0
    if map_data is not None:
        for turn, region in sd["upgrades_executed"]:
            base_construction_count += 1  # 모든 UPGRADE는 base/HQ 건설/업그레이드
            if region in map_data["strongholds"]:
                # 해당 region이 stronghold인 경우
                # 단, 이미 base가 있었던 stronghold의 업그레이드도 capture로 간주
                stronghold_capture_count += 1

    # ---- Upgrade ----
    upgrade_candidate_count = sum(c for _, c in sd["candidate_upgrades"])
    upgrade_select_count = sum(1 for _, _, _, u in sd["chosen_actions"] if u > 0)
    first_upgrade_turn = next(
        (t for t, _, _, u in sd["chosen_actions"] if u > 0), None
    )

    # ---- Training ----
    train_select_count = sum(1 for _, tr, _, _ in sd["chosen_actions"] if tr > 0)
    train_n_values = [tr for _, tr, _, _ in sd["chosen_actions"] if tr > 0]
    avg_train_n = statistics.mean(train_n_values) if train_n_values else 0.0

    # ---- HQ ----
    hq_distances = [d for _, d in sd["hq_distances_per_turn"]]
    avg_hq_distance = statistics.mean(hq_distances) if hq_distances else 999.0
    min_hq_distance = min(hq_distances) if hq_distances else 999
    hq_adjacent_count = sum(1 for d in hq_distances if d == 1)
    hq_attack_count = sum(1 for d in hq_distances if d == 0)

    # ---- Behavior Distribution (MOVE/TRAIN/UPGRADE/WAIT) ----
    # 각 turn마다 어떤 action이 선택되었는지
    behavior_dist = {"MOVE": 0, "TRAIN": 0, "UPGRADE": 0, "WAIT": 0}
    for turn, tr, mv, up in sd["chosen_actions"]:
        if mv > 0:
            behavior_dist["MOVE"] += 1
        if tr > 0:
            behavior_dist["TRAIN"] += 1
        if up > 0:
            behavior_dist["UPGRADE"] += 1
        if mv == 0 and tr == 0 and up == 0:
            behavior_dist["WAIT"] += 1

    # ---- Unique regions visited ----
    unique_regions_count = len(sd["unique_regions_visited"])

    # ---- Top1/Top2 score statistics ----
    top1_scores = [t1 for _, t1, _ in sd["candidate_scores"]]
    top2_scores = [t2 for _, _, t2 in sd["candidate_scores"]]
    top1_gaps = [t1 - t2 for _, t1, t2 in sd["candidate_scores"]]
    avg_top1 = statistics.mean(top1_scores) if top1_scores else 0.0
    avg_top2 = statistics.mean(top2_scores) if top2_scores else 0.0
    avg_top1_top2_gap = statistics.mean(top1_gaps) if top1_gaps else 0.0

    return {
        # Movement
        "avg_moves_per_turn": round(avg_moves_per_turn, 4),
        "move_select_rate": round(move_select_rate, 4),
        "first_move_turn": first_move_turn if first_move_turn is not None else "N/A",
        "avg_move_distance": round(avg_move_distance, 4),
        "avg_hq_approach": round(avg_hq_approach, 4),
        # Stronghold
        "strongholds_visit_count": strongholds_visit_count,
        "first_stronghold_visit": first_stronghold_visit if first_stronghold_visit is not None else "N/A",
        "stronghold_occupied_turns": strongholds_visit_count,
        "stronghold_capture_count": stronghold_capture_count,
        # Upgrade
        "upgrade_candidate_count": upgrade_candidate_count,
        "upgrade_select_count": upgrade_select_count,
        "first_upgrade_turn": first_upgrade_turn if first_upgrade_turn is not None else "N/A",
        "base_construction_count": base_construction_count,
        # Training
        "train_select_count": train_select_count,
        "avg_train_n": round(avg_train_n, 4),
        # HQ
        "avg_hq_distance": round(avg_hq_distance, 4),
        "min_hq_distance": min_hq_distance,
        "hq_adjacent_count": hq_adjacent_count,
        "hq_attack_count": hq_attack_count,
        # Behavior Distribution
        "behavior_move": behavior_dist["MOVE"],
        "behavior_train": behavior_dist["TRAIN"],
        "behavior_upgrade": behavior_dist["UPGRADE"],
        "behavior_wait": behavior_dist["WAIT"],
        # Unique regions
        "unique_regions_visited": unique_regions_count,
        # Score statistics
        "avg_top1_score": round(avg_top1, 4),
        "avg_top2_score": round(avg_top2, 4),
        "avg_top1_top2_gap": round(avg_top1_top2_gap, 4),
        # [NEW] Gold metrics
        "gold_start": sd["gold_time_series"][0][1] if sd["gold_time_series"] else 500,
        "gold_end": sd["gold_time_series"][-1][1] if sd["gold_time_series"] else 500,
        "gold_min": min((g for _, g, _, _ in sd["gold_time_series"]), default=500),
        "gold_max": max((g for _, g, _, _ in sd["gold_time_series"]), default=500),
        "avg_gold": statistics.mean([g for _, g, _, _ in sd["gold_time_series"]]) if sd["gold_time_series"] else 500.0,
        "avg_income": statistics.mean([i for _, _, i, _ in sd["gold_time_series"]]) if sd["gold_time_series"] else 0.0,
        "avg_upkeep": statistics.mean([u for _, _, _, u in sd["gold_time_series"]]) if sd["gold_time_series"] else 0.0,
        # [NEW] Action Rank Distribution
        "avg_action_rank": statistics.mean([r for _, r, _ in sd["chosen_action_ranks"]]) if sd["chosen_action_ranks"] else 999.0,
        "min_action_rank": min((r for _, r, _ in sd["chosen_action_ranks"]), default=999),
        "max_action_rank": max((r for _, r, _ in sd["chosen_action_ranks"]), default=999),
        "total_candidates_considered": sum(t for _, _, t in sd["chosen_action_ranks"]),
        # [NEW] Contribution Distribution summary (aggregated per match)
        "contrib_move_cost_mean": 0.0,  # placeholder - filled in analyze_value_dir
        "contrib_train_n_mean": 0.0,    # placeholder
        "contrib_turns_to_enemy_hq_mean": 0.0,  # placeholder
        "contrib_remaining_gold_mean": 0.0  # placeholder
    }


# =============================================================================
# 3. Feature/Contribution/Final Score Distribution
# =============================================================================

def compute_distributions(log_path):
    """로그에서 Feature/Contribution/Final Score Distribution 계산"""
    with open(log_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    feature_values = defaultdict(list)
    contribution_values = defaultdict(list)
    final_scores = []

    for line in lines:
        for side in ANALYZE_SIDES:
            debug_prefix = f"# Debug {side}:"
            if line.startswith(debug_prefix):
                try:
                    json_str = line[len(debug_prefix):].strip()
                    debug_obj = json.loads(json_str)

                    # Feature dump
                    if "type" in debug_obj and "feature_dump" in debug_obj:
                        ftype = debug_obj["type"]
                        for k, v in debug_obj["feature_dump"].items():
                            key = f"{ftype}_{k}"
                            feature_values[key].append(v)

                    # Contribution dump
                    if "contribution_dump" in debug_obj:
                        for k, v in debug_obj["contribution_dump"].items():
                            contribution_values[k].append(v)

                    # Final Score from candidate selection
                    if "best_score" in debug_obj:
                        final_scores.append(debug_obj["best_score"])
                except (json.JSONDecodeError, KeyError, ValueError):
                    pass

    return {
        "feature_values": {k: list(v) for k, v in feature_values.items()},
        "contribution_values": {k: list(v) for k, v in contribution_values.items()},
        "final_scores": final_scores
    }


# =============================================================================
# 4. Main Analysis
# =============================================================================

def analyze_value_dir(value_dir):
    """하나의 weight value 디렉토리 내 모든 match 분석"""
    log_files = sorted(value_dir.glob("match_*.log"))
    if not log_files:
        return None

    all_metrics = []
    all_winners = []
    all_reasons = []
    all_feature_values = defaultdict(list)
    all_contribution_values = defaultdict(list)
    all_final_scores = []

    for log_file in log_files:
        try:
            parsed = parse_log(log_file)
            if parsed is None:
                continue
            result = parsed["result"]
            all_winners.append(result.get("winner"))
            all_reasons.append(result.get("reason"))

            # side별 metrics
            max_turn = max(
                (max(t for t, _, _, _ in parsed["side_data"][s]["chosen_actions"]) if parsed["side_data"][s]["chosen_actions"] else 0)
                for s in ANALYZE_SIDES
            ) or 200

            side_metrics = {}
            for side in ANALYZE_SIDES:
                m = compute_behavior_metrics(parsed["side_data"][side], max_turn, parsed["map_data"])
                side_metrics[side] = m
            all_metrics.append(side_metrics)

            # distributions
            dist = compute_distributions(log_file)
            for k, v in dist["feature_values"].items():
                all_feature_values[k].extend(v)
            for k, v in dist["contribution_values"].items():
                all_contribution_values[k].extend(v)
            all_final_scores.extend(dist["final_scores"])

        except Exception as e:
            print(f"    [WARN] {log_file.name} 파싱 실패: {e}")
            continue

    if not all_metrics:
        return None

    # side별 metric 집계 (LEFT/RIGHT 평균)
    aggregated = {}
    metric_keys = list(all_metrics[0]["LEFT"].keys())
    for key in metric_keys:
        values = []
        for m in all_metrics:
            for s in ANALYZE_SIDES:
                v = m[s].get(key)
                if v is not None and v != "N/A":
                    if isinstance(v, (int, float)):
                        values.append(v)
        if values:
            aggregated[key] = round(statistics.mean(values), 4)
        else:
            aggregated[key] = "N/A"

    # Behavior Distribution 집계
    behavior_dist = {"MOVE": 0, "TRAIN": 0, "UPGRADE": 0, "WAIT": 0}
    for m in all_metrics:
        for s in ANALYZE_SIDES:
            behavior_dist["MOVE"] += m[s]["behavior_move"]
            behavior_dist["TRAIN"] += m[s]["behavior_train"]
            behavior_dist["UPGRADE"] += m[s]["behavior_upgrade"]
            behavior_dist["WAIT"] += m[s]["behavior_wait"]
    total_behavior = sum(behavior_dist.values()) or 1

    behavior_pct = {
        k: round(100.0 * v / total_behavior, 2) for k, v in behavior_dist.items()
    }

    # Feature Distribution
    feature_dist = {
        k: {
            "mean": round(statistics.mean(v), 4) if v else 0,
            "std": round(statistics.stdev(v), 4) if len(v) > 1 else 0,
            "min": round(min(v), 4) if v else 0,
            "max": round(max(v), 4) if v else 0
        }
        for k, v in all_feature_values.items()
    }

    # Contribution Distribution (Dominance 계산용)
    contrib_dist = {}
    contrib_abs_means = {}
    total_contrib_abs = 0
    for k, v in all_contribution_values.items():
        if v:
            abs_mean = statistics.mean([abs(x) for x in v])
            contrib_dist[k] = {
                "mean": round(statistics.mean(v), 4),
                "abs_mean": round(abs_mean, 4),
                "std": round(statistics.stdev(v), 4) if len(v) > 1 else 0
            }
            contrib_abs_means[k] = abs_mean
            total_contrib_abs += abs_mean

    # Dominance: 가장 큰 contribution의 비율
    dominance = {}
    if contrib_abs_means and total_contrib_abs > 0:
        for k, abs_mean in contrib_abs_means.items():
            dominance[k] = round(100.0 * abs_mean / total_contrib_abs, 2)
        dominance_sorted = sorted(dominance.items(), key=lambda x: -x[1])
        top_dominance = dominance_sorted[0]
    else:
        top_dominance = ("N/A", 0)
        dominance = {}

    # Final Score Distribution
    final_score_dist = {
        "mean": round(statistics.mean(all_final_scores), 4) if all_final_scores else 0,
        "std": round(statistics.stdev(all_final_scores), 4) if len(all_final_scores) > 1 else 0,
        "min": round(min(all_final_scores), 4) if all_final_scores else 0,
        "max": round(max(all_final_scores), 4) if all_final_scores else 0
    }

    # Update aggregated with contribution means (from aggregated contribution_values)
    # NOTE: contribution_dump keys have "contrib_" prefix (e.g., "contrib_train_n")
    # This was a BUG: loop was looking for keys without prefix
    contrib_key_mapping = {
        "contrib_move_cost": "move_cost",
        "contrib_train_n": "train_n",
        "contrib_train_cost": "train_cost",
        "contrib_turns_to_enemy_hq": "turns_to_enemy_hq",
        "contrib_remaining_gold_after_action": "remaining_gold_after_action",
        "contrib_upgrade_is_stronghold": "upgrade_is_stronghold",
        "contrib_upgrade_cost": "upgrade_cost",
        "contrib_upgrade_remaining_gold": "upgrade_remaining_gold",
        "contrib_is_stronghold": "is_stronghold"
    }
    for actual_key, base_key in contrib_key_mapping.items():
        if actual_key in all_contribution_values and all_contribution_values[actual_key]:
            key_name = f"contrib_{base_key}_mean"
            aggregated[key_name] = round(statistics.mean(all_contribution_values[actual_key]), 4)

    # Win/Lose/Draw
    winner_counts = Counter(all_winners)
    win = winner_counts.get("LEFT", 0) + winner_counts.get("RIGHT", 0)
    # LEFT는 LEFT의 승리, RIGHT는 RIGHT의 승리
    # 우리 분석은 LEFT와 RIGHT 모두 동일 weight를 사용
    # 승률 = LEFT 승리 / 전체 (LEFT 기준)
    win_left = winner_counts.get("LEFT", 0)
    win_right = winner_counts.get("RIGHT", 0)
    draw = sum(1 for r in all_reasons if r == "TURN_LIMIT")
    total = len(all_winners)
    win_rate = round(100.0 * win_left / total, 2) if total else 0
    draw_rate = round(100.0 * draw / total, 2) if total else 0
    lose_rate = round(100.0 * win_right / total, 2) if total else 0

    return {
        "match_count": total,
        "win": win_left,
        "lose": win_right,
        "draw": draw,
        "win_rate_pct": win_rate,
        "draw_rate_pct": draw_rate,
        "lose_rate_pct": lose_rate,
        "behavior_distribution": behavior_pct,
        "behavior_counts": behavior_dist,
        "feature_distribution": feature_dist,
        "contribution_distribution": contrib_dist,
        "dominance": dominance,
        "top_dominance": {"feature": top_dominance[0], "pct": top_dominance[1]},
        "final_score_distribution": final_score_dist,
        "behavior_metrics": aggregated
    }


def main():
    print("="*70)
    print("NYPC 2026 STEP 6E - Adaptive Weight Sweep Framework")
    print("="*70)
    print(f"Sweep Base Dir: {SWEEP_BASE_DIR}")
    print(f"Report Dir: {REPORT_DIR}")

    if not SWEEP_BASE_DIR.exists():
        print(f"[ERROR] Sweep 디렉토리 없음: {SWEEP_BASE_DIR}")
        print("먼저 python scripts/weight_sweep_runner.py 를 실행하세요.")
        return

    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    # 각 weight_sweep_* 디렉토리 처리
    sweep_results = {}
    for sweep_dir in sorted(SWEEP_BASE_DIR.glob("w_*")):
        if not sweep_dir.is_dir():
            continue
        weight_name = sweep_dir.name
        print(f"\n[Sweep] {weight_name}")

        sweep_data = {}
        for value_dir in sorted(sweep_dir.glob(f"{weight_name}_*")):
            if not value_dir.is_dir():
                continue
            value_str = value_dir.name.replace(f"{weight_name}_", "")
            try:
                value = float(value_str) if "." in value_str else int(value_str)
            except ValueError:
                value = value_str

            print(f"  [Value] {weight_name}={value} 분석 중...")
            result = analyze_value_dir(value_dir)
            if result is None:
                print(f"    [SKIP] {value_dir} - 로그 없음")
                continue

            sweep_data[value] = result
            print(f"    Match: {result['match_count']}, "
                  f"Win/Draw/Lose: {result['win']}/{result['draw']}/{result['lose']}, "
                  f"MOVE%: {result['behavior_distribution']['MOVE']}, "
                  f"TRAIN%: {result['behavior_distribution']['TRAIN']}, "
                  f"UPGRADE%: {result['behavior_distribution']['UPGRADE']}, "
                  f"Top Dom: {result['top_dominance']['feature']}({result['top_dominance']['pct']}%)")

        sweep_results[weight_name] = sweep_data

    # JSON 저장
    summary_json_path = BEHAVIOR_SUMMARY_JSON
    with open(summary_json_path, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "sweeps": sweep_results
        }, f, indent=2, ensure_ascii=False)
    print(f"\n[OK] JSON Summary 저장: {summary_json_path}")

    # CSV 저장 (가로형)
    csv_path = BEHAVIOR_SUMMARY_CSV
    with open(csv_path, "w", encoding="utf-8") as f:
        # Header
        headers = [
            "weight_name", "weight_value", "match_count",
            "win", "lose", "draw", "win_rate_pct", "draw_rate_pct", "lose_rate_pct",
            # Behavior Distribution (%)
            "behavior_move_pct", "behavior_train_pct", "behavior_upgrade_pct", "behavior_wait_pct",
            "behavior_move_count", "behavior_train_count", "behavior_upgrade_count", "behavior_wait_count",
            # Behavior Metrics - Movement
            "avg_moves_per_turn", "move_select_rate", "first_move_turn", "avg_move_distance", "avg_hq_approach",
            # Stronghold
            "strongholds_visit_count", "first_stronghold_visit", "stronghold_occupied_turns", "stronghold_capture_count",
            # Upgrade / Base construction
            "upgrade_candidate_count", "upgrade_select_count", "first_upgrade_turn", "base_construction_count",
            # Training
            "train_select_count", "avg_train_n",
            # HQ
            "avg_hq_distance", "min_hq_distance", "hq_adjacent_count", "hq_attack_count",
            # Unique regions
            "unique_regions_visited",
            # Candidate score statistics
            "avg_top1_score", "avg_top2_score", "avg_top1_top2_gap",
            # Final Score Distribution
            "final_score_mean", "final_score_std", "final_score_min", "final_score_max",
            # [NEW] Gold metrics
            "gold_start", "gold_end", "gold_min", "gold_max", "avg_gold", "avg_income", "avg_upkeep",
            # [NEW] Action Rank Distribution
            "avg_action_rank", "min_action_rank", "max_action_rank", "total_candidates_considered",
            # [NEW] Contribution means
            "contrib_move_cost_mean", "contrib_train_n_mean", "contrib_turns_to_enemy_hq_mean",
            "contrib_remaining_gold_mean", "contrib_train_cost_mean",
            # Dominance
            "top_dominance_feature", "top_dominance_pct"
        ]
        f.write(",".join(headers) + "\n")

        for weight_name, sweep_data in sweep_results.items():
            for value, result in sweep_data.items():
                row = [
                    weight_name, value, result["match_count"],
                    result["win"], result["lose"], result["draw"],
                    result["win_rate_pct"], result["draw_rate_pct"], result["lose_rate_pct"],
                    # Behavior Distribution
                    result["behavior_distribution"]["MOVE"],
                    result["behavior_distribution"]["TRAIN"],
                    result["behavior_distribution"]["UPGRADE"],
                    result["behavior_distribution"]["WAIT"],
                    result["behavior_counts"]["MOVE"],
                    result["behavior_counts"]["TRAIN"],
                    result["behavior_counts"]["UPGRADE"],
                    result["behavior_counts"]["WAIT"],
                ]
                # Behavior Metrics
                bm = result["behavior_metrics"]
                row.extend([
                    bm.get("avg_moves_per_turn", "N/A"),
                    bm.get("move_select_rate", "N/A"),
                    bm.get("first_move_turn", "N/A"),
                    bm.get("avg_move_distance", "N/A"),
                    bm.get("avg_hq_approach", "N/A"),
                    bm.get("strongholds_visit_count", "N/A"),
                    bm.get("first_stronghold_visit", "N/A"),
                    bm.get("stronghold_occupied_turns", "N/A"),
                    bm.get("stronghold_capture_count", "N/A"),
                    bm.get("upgrade_candidate_count", "N/A"),
                    bm.get("upgrade_select_count", "N/A"),
                    bm.get("first_upgrade_turn", "N/A"),
                    bm.get("base_construction_count", "N/A"),
                    bm.get("train_select_count", "N/A"),
                    bm.get("avg_train_n", "N/A"),
                    bm.get("avg_hq_distance", "N/A"),
                    bm.get("min_hq_distance", "N/A"),
                    bm.get("hq_adjacent_count", "N/A"),
                    bm.get("hq_attack_count", "N/A"),
                    bm.get("unique_regions_visited", "N/A"),
                    bm.get("avg_top1_score", "N/A"),
                    bm.get("avg_top2_score", "N/A"),
                    bm.get("avg_top1_top2_gap", "N/A"),
                ])
                # Final Score
                fsd = result["final_score_distribution"]
                row.extend([
                    fsd["mean"], fsd["std"], fsd["min"], fsd["max"]
                ])
                # [NEW] Gold metrics
                row.extend([
                    bm.get("gold_start", "N/A"),
                    bm.get("gold_end", "N/A"),
                    bm.get("gold_min", "N/A"),
                    bm.get("gold_max", "N/A"),
                    bm.get("avg_gold", "N/A"),
                    bm.get("avg_income", "N/A"),
                    bm.get("avg_upkeep", "N/A"),
                ])
                # [NEW] Action Rank Distribution
                row.extend([
                    bm.get("avg_action_rank", "N/A"),
                    bm.get("min_action_rank", "N/A"),
                    bm.get("max_action_rank", "N/A"),
                    bm.get("total_candidates_considered", "N/A"),
                ])
                # [NEW] Contribution means
                row.extend([
                    bm.get("contrib_move_cost_mean", "N/A"),
                    bm.get("contrib_train_n_mean", "N/A"),
                    bm.get("contrib_turns_to_enemy_hq_mean", "N/A"),
                    bm.get("contrib_remaining_gold_mean", "N/A"),
                    bm.get("contrib_train_cost_mean", "N/A"),
                ])
                # Dominance
                row.extend([
                    result["top_dominance"]["feature"],
                    result["top_dominance"]["pct"]
                ])
                f.write(",".join(str(x) for x in row) + "\n")

    print(f"[OK] CSV Summary 저장: {csv_path}")

    print("\n" + "="*70)
    print("Behavior Benchmark 완료")
    print("="*70)
    print("\n다음 단계:")
    print(f"  python scripts/weight_sweep_report.py    # 최종 Report + Ranking")


if __name__ == "__main__":
    main()
