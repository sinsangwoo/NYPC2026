"""
NYPC 2026 STEP 3B - Action Meta Analysis
실제 로그 기반으로 행동 패턴 분석
"""

import json
import re
import numpy as np
import pandas as pd
from pathlib import Path
from collections import defaultdict, Counter

# 경로 설정
PROJECT_ROOT = Path(__file__).parent.parent
LOGS_RAW = PROJECT_ROOT / "logs" / "raw"
OUTPUT_DIR = PROJECT_ROOT / "visualizations"
OUTPUT_DIR.mkdir(exist_ok=True)

def parse_log_file(log_path):
    """단일 로그 파일 파싱"""
    actions = []
    turn_events = defaultdict(list)
    current_turn = None
    
    with open(log_path, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f]
    
    for line in lines:
        # 턴 시작
        if line.startswith("TURN "):
            current_turn = int(line.split()[1])
        
        # LEFT/RIGHT 명령
        elif line.startswith("MOVE "):
            if current_turn:
                parts = line.split()
                warrior_id = parts[1]
                target_node = int(parts[2])
                actions.append({
                    "turn": current_turn,
                    "action": "MOVE",
                    "warrior_id": warrior_id,
                    "target_node": target_node,
                    "side": "LEFT" if warrior_id.startswith("A") else "RIGHT"
                })
                turn_events[current_turn].append("MOVE")
        
        # 전투/피해 이벤트
        elif line.startswith("DAMAGE "):
            if current_turn:
                parts = line.split()
                cause = parts[1]
                warrior_id = parts[2]
                damage = int(parts[3])
                actions.append({
                    "turn": current_turn,
                    "action": "DAMAGE",
                    "warrior_id": warrior_id,
                    "damage": damage,
                    "cause": cause,
                    "side": "LEFT" if warrior_id.startswith("A") else "RIGHT"
                })
                turn_events[current_turn].append("DAMAGE")
        
        # 공성 이벤트
        elif line.startswith("SIEGE "):
            if current_turn:
                parts = line.split()
                side = parts[1]
                region = int(parts[2])
                damage = int(parts[3])
                actions.append({
                    "turn": current_turn,
                    "action": "SIEGE",
                    "side": side,
                    "region": region,
                    "damage": damage
                })
                turn_events[current_turn].append("SIEGE")
        
        # 게임 결과
        elif line.startswith("WINNER "):
            winner = line.split()[1]
        elif line.startswith("END_REASON "):
            end_reason = line.split()[1]
    
    return {
        "actions": actions,
        "turn_events": turn_events,
        "winner": winner if 'winner' in locals() else None,
        "end_reason": end_reason if 'end_reason' in locals() else None
    }

def main():
    print("=" * 60)
    print("NYPC 2026 STEP 3B - Action Meta Analysis")
    print("=" * 60)
    
    # 모든 로그 파일 처리
    all_actions = []
    all_turn_events = defaultdict(list)
    match_action_counts = defaultdict(Counter)
    match_info = []
    
    log_files = list(LOGS_RAW.glob("game_*.log"))
    print(f"\n--- Processing {len(log_files)} log files ---")
    
    for log_file in log_files:
        match_id = int(log_file.stem.split("_")[1])
        print(f"  Processing match {match_id}...", end="\r")
        
        parsed = parse_log_file(log_file)
        
        # 액션 수집
        all_actions.extend(parsed["actions"])
        
        # 턴 이벤트 수집
        for turn, events in parsed["turn_events"].items():
            all_turn_events[turn].extend(events)
        
        # 경기별 액션 카운트
        action_counter = Counter([a["action"] for a in parsed["actions"]])
        match_action_counts[match_id] = action_counter
        
        # 경기 정보
        match_info.append({
            "match_id": match_id,
            "winner": parsed["winner"],
            "end_reason": parsed["end_reason"],
            "total_turns": max(parsed["turn_events"].keys()) if parsed["turn_events"] else 0
        })
    
    print(f"\n  Done! Total actions: {len(all_actions)}")
    
    # --- 1. Action Inventory ---
    print("\n--- 1. Action Inventory ---")
    action_counter = Counter([a["action"] for a in all_actions])
    action_inventory = []
    
    for action, count in action_counter.most_common():
        # 발생 경기 수
        match_count = sum(1 for c in match_action_counts.values() if action in c)
        # 턴 분포
        turns = [a["turn"] for a in all_actions if a["action"] == action]
        turn_mean = np.mean(turns) if turns else 0
        turn_std = np.std(turns) if turns else 0
        
        action_inventory.append({
            "action": action,
            "total_count": count,
            "match_count": match_count,
            "turn_mean": turn_mean,
            "turn_std": turn_std,
            "min_turn": min(turns) if turns else 0,
            "max_turn": max(turns) if turns else 0
        })
    
    action_inventory_df = pd.DataFrame(action_inventory)
    print(action_inventory_df.to_string(index=False))
    action_inventory_df.to_csv(OUTPUT_DIR / "action_inventory.csv", index=False, encoding="utf-8-sig")
    
    # --- 2. Turn Action Distribution ---
    print("\n--- 2. Turn Action Distribution ---")
    turn_action_dist = []
    max_turn = max(all_turn_events.keys()) if all_turn_events else 0
    
    for turn in range(1, max_turn + 1):
        events = all_turn_events.get(turn, [])
        if not events:
            continue
        
        total = len(events)
        counter = Counter(events)
        
        row = {"turn": turn, "total_actions": total}
        for action, cnt in counter.items():
            row[f"{action}_count"] = cnt
            row[f"{action}_ratio"] = cnt / total
        
        turn_action_dist.append(row)
    
    turn_action_df = pd.DataFrame(turn_action_dist)
    turn_action_df.to_csv(OUTPUT_DIR / "turn_action_distribution.csv", index=False, encoding="utf-8-sig")
    print(f"Saved turn action distribution for {len(turn_action_df)} turns")
    
    # --- 3. Action Transition Matrix ---
    print("\n--- 3. Action Transition Matrix ---")
    # 턴별 액션 시퀀스 생성 (단순화: 턴당 대표 액션)
    turn_sequences = []
    for match_id in sorted(match_action_counts.keys()):
        # 해당 경기의 액션만 필터링
        match_actions = [a for a in all_actions if a["turn"] <= 200]  # 200턴까지만
        # 턴별로 그룹화
        turn_actions = defaultdict(list)
        for a in match_actions:
            turn_actions[a["turn"]].append(a["action"])
        
        # 턴 순서대로 대표 액션 선택 (가장 빈번한 것)
        sequence = []
        for turn in sorted(turn_actions.keys()):
            acts = turn_actions[turn]
            if acts:
                # 가장 빈번한 액션
                most_common = Counter(acts).most_common(1)[0][0]
                sequence.append(most_common)
        
        turn_sequences.append(sequence)
    
    # 전이 행렬 계산
    transitions = defaultdict(Counter)
    all_actions_list = list(action_counter.keys())
    
    for seq in turn_sequences:
        for i in range(len(seq) - 1):
            prev = seq[i]
            curr = seq[i + 1]
            transitions[prev][curr] += 1
    
    # DataFrame으로 변환
    transition_matrix = []
    for prev in all_actions_list:
        row = {"from": prev}
        total = sum(transitions[prev].values())
        for curr in all_actions_list:
            cnt = transitions[prev].get(curr, 0)
            row[f"to_{curr}"] = cnt
            row[f"to_{curr}_ratio"] = cnt / total if total > 0 else 0
        transition_matrix.append(row)
    
    transition_df = pd.DataFrame(transition_matrix)
    transition_df.to_csv(OUTPUT_DIR / "action_transition_matrix.csv", index=False, encoding="utf-8-sig")
    print("Saved action transition matrix")
    
    # --- 4. Event Before Action ---
    print("\n--- 4. Event Before Action ---")
    # 각 경기에서 첫 이벤트 찾기
    first_events = []
    
    for match_id in sorted(match_action_counts.keys()):
        match_actions = [a for a in all_actions if a["turn"] <= 200]
        # 턴 순서대로 정렬
        match_actions_sorted = sorted(match_actions, key=lambda x: x["turn"])
        
        first_damage_turn = None
        first_combat_turn = None
        first_siege_turn = None
        
        for a in match_actions_sorted:
            if a["action"] == "DAMAGE" and first_damage_turn is None:
                first_damage_turn = a["turn"]
            if a["action"] == "DAMAGE" and a.get("cause") == "COMBAT" and first_combat_turn is None:
                first_combat_turn = a["turn"]
            if a["action"] == "SIEGE" and first_siege_turn is None:
                first_siege_turn = a["turn"]
        
        first_events.append({
            "match_id": match_id,
            "first_damage_turn": first_damage_turn,
            "first_combat_turn": first_combat_turn,
            "first_siege_turn": first_siege_turn
        })
    
    # 각 이벤트 직전 3턴 액션 분석
    event_before_analysis = []
    event_types = ["first_damage", "first_combat", "first_siege"]
    
    for event_type in event_types:
        turn_key = f"{event_type}_turn"
        before_actions = {1: [], 2: [], 3: []}
        
        for fe in first_events:
            event_turn = fe[turn_key]
            if event_turn is None:
                continue
            
            # 해당 경기의 액션
            match_id = fe["match_id"]
            match_actions = [a for a in all_actions if a["turn"] <= 200]
            
            for offset in [1, 2, 3]:
                target_turn = event_turn - offset
                if target_turn < 1:
                    continue
                
                # 해당 턴의 액션
                turn_acts = [a["action"] for a in match_actions if a["turn"] == target_turn]
                before_actions[offset].extend(turn_acts)
        
        # 결과 정리
        for offset in [1, 2, 3]:
            counter = Counter(before_actions[offset])
            for action, cnt in counter.most_common():
                event_before_analysis.append({
                    "event_type": event_type,
                    "before_turns": offset,
                    "action": action,
                    "count": cnt
                })
    
    event_before_df = pd.DataFrame(event_before_analysis)
    event_before_df.to_csv(OUTPUT_DIR / "event_before_action.csv", index=False, encoding="utf-8-sig")
    print("Saved event before action analysis")
    
    # --- 5. Node Action Analysis ---
    print("\n--- 5. Node Action Analysis ---")
    node_actions = defaultdict(Counter)
    
    for a in all_actions:
        if a["action"] == "MOVE" and "target_node" in a:
            node = a["target_node"]
            node_actions[node]["MOVE"] += 1
        elif a["action"] == "DAMAGE":
            # 피해는 노드 정보가 없으므로 제외
            pass
        elif a["action"] == "SIEGE" and "region" in a:
            node = a["region"]
            node_actions[node]["SIEGE"] += 1
    
    # DataFrame으로 변환
    node_action_list = []
    for node in sorted(node_actions.keys()):
        counter = node_actions[node]
        total = sum(counter.values())
        row = {"node": node, "total_actions": total}
        for action, cnt in counter.items():
            row[f"{action}_count"] = cnt
            row[f"{action}_ratio"] = cnt / total
        node_action_list.append(row)
    
    node_action_df = pd.DataFrame(node_action_list)
    node_action_df.to_csv(OUTPUT_DIR / "node_action_analysis.csv", index=False, encoding="utf-8-sig")
    print(f"Saved node action analysis for {len(node_action_df)} nodes")
    
    # --- 6. Decision Point Detection ---
    print("\n--- 6. Decision Point Detection ---")
    decision_points = []
    
    # 1. 첫 피해 전후 (적 발견 추정)
    decision_points.append({
        "decision_point": "First Damage (Enemy Detected)",
        "trigger": "First damage event occurs",
        "turn_range": "Around first_damage_turn",
        "evidence": "Damage events start appearing",
        "priority": "High"
    })
    
    # 2. 첫 공성 전후 (HQ 근처 추정)
    decision_points.append({
        "decision_point": "First Siege (HQ Proximity)",
        "trigger": "First siege event occurs",
        "turn_range": "Around first_siege_turn",
        "evidence": "Siege events start appearing",
        "priority": "High"
    })
    
    # 3. 초반 이동 후 (1-6턴)
    decision_points.append({
        "decision_point": "Early Exploration End",
        "trigger": "After initial exploration (turn 7+)",
        "turn_range": "Turn 7-12",
        "evidence": "Move count drops significantly",
        "priority": "Medium"
    })
    
    # 4. Stronghold 노드 도착
    decision_points.append({
        "decision_point": "Stronghold Arrival",
        "trigger": "Arrive at stronghold node",
        "turn_range": "Any turn",
        "evidence": "Move to stronghold node (4,5,19,23,24,34,36,38,48,49,53,67,68)",
        "priority": "Medium"
    })
    
    decision_points_df = pd.DataFrame(decision_points)
    decision_points_df.to_csv(OUTPUT_DIR / "decision_points.csv", index=False, encoding="utf-8-sig")
    print("Saved decision point detection")
    
    # --- 7. State → Action Mapping ---
    print("\n--- 7. State → Action Mapping ---")
    state_action_mapping = []
    
    # 관측 가능한 상태만
    state_action_mapping.append({
        "state": "No enemies nearby (no damage)",
        "observable_evidence": "No damage events",
        "common_action": "MOVE",
        "evidence_count": sum(1 for a in all_actions if a["action"] == "MOVE")
    })
    
    state_action_mapping.append({
        "state": "Enemy present (combat damage)",
        "observable_evidence": "Combat damage events",
        "common_action": "DAMAGE (combat)",
        "evidence_count": sum(1 for a in all_actions if a["action"] == "DAMAGE" and a.get("cause") == "COMBAT")
    })
    
    state_action_mapping.append({
        "state": "Near enemy HQ (siege possible)",
        "observable_evidence": "Siege events",
        "common_action": "SIEGE",
        "evidence_count": sum(1 for a in all_actions if a["action"] == "SIEGE")
    })
    
    state_action_df = pd.DataFrame(state_action_mapping)
    state_action_df.to_csv(OUTPUT_DIR / "state_action_mapping.csv", index=False, encoding="utf-8-sig")
    print("Saved state → action mapping")
    
    # --- 8. Baseline Action Set ---
    print("\n--- 8. Baseline Action Set ---")
    baseline_action_set = [
        {"action": "MOVE", "required": True, "reason": "Essential for exploration and positioning"},
        {"action": "ATTACK (implied by DAMAGE)", "required": True, "reason": "Essential for combat"},
        {"action": "SIEGE", "required": True, "reason": "Essential for winning (HQ destruction)"},
        {"action": "WAIT", "required": False, "reason": "Not observed in sample logs, but may be useful"}
    ]
    baseline_action_df = pd.DataFrame(baseline_action_set)
    baseline_action_df.to_csv(OUTPUT_DIR / "baseline_action_set.csv", index=False, encoding="utf-8-sig")
    print("Saved baseline action set")
    
    # --- 9. Rule Candidate 추출 ---
    print("\n--- 9. Rule Candidate 추출 ---")
    rule_candidates = [
        {
            "rule": "If no enemies are visible, move towards center/opponent HQ",
            "evidence": "Early game (turn 1-6) has high move count",
            "applicable_state": "No damage events, early game",
            "expected_effect": "Reach combat/siege positions faster",
            "implementation_difficulty": "Low"
        },
        {
            "rule": "If enemies are in combat range, attack",
            "evidence": "Damage events cluster around turn 6-12",
            "applicable_state": "Combat damage occurring",
            "expected_effect": "Eliminate enemy units",
            "implementation_difficulty": "Low"
        },
        {
            "rule": "If near enemy HQ, initiate siege",
            "evidence": "Siege events lead to HQ_DESTROYED end",
            "applicable_state": "Near enemy HQ",
            "expected_effect": "Destroy enemy HQ to win",
            "implementation_difficulty": "Medium"
        }
    ]
    rule_candidates_df = pd.DataFrame(rule_candidates)
    rule_candidates_df.to_csv(OUTPUT_DIR / "rule_candidates.csv", index=False, encoding="utf-8-sig")
    print("Saved rule candidates")
    
    # --- 최종 요약 ---
    print("\n" + "=" * 60)
    print("Action Meta Analysis Complete!")
    print(f"Results saved to: {OUTPUT_DIR}")
    print("=" * 60)
    
    return {
        "action_inventory": action_inventory_df,
        "turn_action_dist": turn_action_df,
        "transition_matrix": transition_df,
        "event_before": event_before_df,
        "node_action": node_action_df,
        "decision_points": decision_points_df,
        "state_action": state_action_df,
        "baseline_action": baseline_action_df,
        "rule_candidates": rule_candidates_df
    }

if __name__ == "__main__":
    main()