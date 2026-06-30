#!/usr/bin/env python3
"""
100경기 데이터 간단 분석 스크립트
STEP 2.5 - features.csv 분석
"""

import csv
from pathlib import Path
import statistics
from collections import defaultdict

def main():
    project_root = Path(__file__).parent.parent
    features_path = project_root / "logs" / "analysis" / "features.csv"
    
    if not features_path.exists():
        print("features.csv가 없습니다! 먼저 analyze_logs.py를 실행하세요.")
        return
    
    print("=" * 60)
    print("📊 100경기 데이터 분석 결과")
    print("=" * 60)
    
    # 데이터 읽기
    matches = []
    with open(features_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # 숫자로 변환
            for key in row:
                if key in ["winner", "total_turns", "train_count", 
                          "total_damage_combat", "total_damage_turret", 
                          "total_damage_hunger", "siege_count", 
                          "total_moves", "hunger_index"]:
                    try:
                        row[key] = int(row[key]) if row[key] else 0
                    except ValueError:
                        row[key] = 0
                elif key in ["avg_time_left", "avg_time_right", "avg_moves_per_turn",
                            "turret_risk", "siege_efficiency", "training_efficiency"]:
                    try:
                        row[key] = float(row[key]) if row[key] else 0.0
                    except ValueError:
                        row[key] = 0.0
                else:
                    # Infinity 처리
                    if row[key] == "inf":
                        row[key] = float("inf")
                    elif row[key].replace(".", "", 1).isdigit():
                        try:
                            row[key] = float(row[key])
                        except ValueError:
                            pass
            matches.append(row)
    
    print(f"\n총 경기 수: {len(matches)}")
    print()
    
    # 1. 승리 결과
    print("--- 🎯 승리 결과 ---")
    winner_counts = defaultdict(int)
    reason_counts = defaultdict(int)
    for m in matches:
        winner = m["winner"]
        if winner == -1:
            winner_counts["무승부 (DRAW)"] += 1
        elif winner == 0:
            winner_counts["LEFT 승리"] += 1
        elif winner == 1:
            winner_counts["RIGHT 승리"] += 1
        reason_counts[m["reason"]] += 1
    
    for key, count in winner_counts.items():
        print(f"  {key}: {count}경기 ({count/len(matches)*100:.1f}%)")
    print()
    print("  종료 이유:")
    for key, count in reason_counts.items():
        print(f"    {key}: {count}경기")
    
    # 2. 평균 턴 수
    print()
    print("--- ⏱️ 턴 수 ---")
    total_turns = [m["total_turns"] for m in matches]
    print(f"  평균: {statistics.mean(total_turns):.1f}턴")
    print(f"  최소: {min(total_turns)}턴")
    print(f"  최대: {max(total_turns)}턴")
    
    # 3. 첫 이벤트 턴
    print()
    print("--- ⚡ 첫 이벤트 턴 ---")
    def get_valid_values(data, key):
        values = []
        for m in data:
            val = m[key]
            if val != float("inf") and val is not None and val != "":
                values.append(val)
        return values
    
    first_train = get_valid_values(matches, "first_train_turn")
    first_damage = get_valid_values(matches, "first_damage_turn")
    first_combat = get_valid_values(matches, "first_combat_turn")
    first_turret = get_valid_values(matches, "first_turret_turn")
    first_hunger = get_valid_values(matches, "first_hunger_turn")
    first_siege = get_valid_values(matches, "first_siege_turn")
    
    if first_train:
        print(f"  첫 TRAIN: 평균 {statistics.mean(first_train):.1f}턴 (발생률: {len(first_train)/len(matches)*100:.1f}%)")
    else:
        print(f"  첫 TRAIN: 없음 (0%)")
    if first_damage:
        print(f"  첫 DAMAGE: 평균 {statistics.mean(first_damage):.1f}턴 (발생률: {len(first_damage)/len(matches)*100:.1f}%)")
    if first_combat:
        print(f"  첫 COMBAT: 평균 {statistics.mean(first_combat):.1f}턴 (발생률: {len(first_combat)/len(matches)*100:.1f}%)")
    if first_turret:
        print(f"  첫 TURRET: 평균 {statistics.mean(first_turret):.1f}턴 (발생률: {len(first_turret)/len(matches)*100:.1f}%)")
    if first_hunger:
        print(f"  첫 HUNGER: 평균 {statistics.mean(first_hunger):.1f}턴 (발생률: {len(first_hunger)/len(matches)*100:.1f}%)")
    if first_siege:
        print(f"  첫 SIEGE: 평균 {statistics.mean(first_siege):.1f}턴 (발생률: {len(first_siege)/len(matches)*100:.1f}%)")
    
    # 4. 전체 개수
    print()
    print("--- 📊 총 개수 ---")
    print(f"  평균 TRAIN 횟수: {statistics.mean([m['train_count'] for m in matches]):.1f}")
    print(f"  평균 COMBAT 데미지: {statistics.mean([m['total_damage_combat'] for m in matches]):.1f}")
    print(f"  평균 TURRET 데미지: {statistics.mean([m['total_damage_turret'] for m in matches]):.1f}")
    print(f"  평균 HUNGER 데미지: {statistics.mean([m['total_damage_hunger'] for m in matches]):.1f}")
    print(f"  평균 SIEGE 횟수: {statistics.mean([m['siege_count'] for m in matches]):.1f}")
    print(f"  평균 총 SIEGE 데미지: {statistics.mean([m['total_siege_damage'] for m in matches]):.1f}")
    print(f"  평균 MOVE 횟수: {statistics.mean([m['total_moves'] for m in matches]):.1f}")
    print(f"  평균 턴당 MOVE: {statistics.mean([m['avg_moves_per_turn'] for m in matches]):.2f}")
    
    # 5. 특별 지표
    print()
    print("--- 💡 게임 메커니즘 지표 ---")
    hunger_matches = [m for m in matches if m["hunger_index"] > 0]
    print(f"  HUNGER 발생 경기: {len(hunger_matches)}경기 ({len(hunger_matches)/len(matches)*100:.1f}%)")
    if hunger_matches:
        print(f"    평균 HUNGER 데미지: {statistics.mean([m['hunger_index'] for m in hunger_matches]):.1f}")
    
    turret_risk_values = [m["turret_risk"] for m in matches if m["total_damage_combat"] + m["total_damage_turret"] + m["total_damage_hunger"] > 0]
    if turret_risk_values:
        print(f"  평균 Turret Risk: {statistics.mean(turret_risk_values):.3f}")
    
    siege_efficiency_values = [m["siege_efficiency"] for m in matches if m["total_damage_combat"] > 0]
    if siege_efficiency_values:
        print(f"  평균 Siege Efficiency: {statistics.mean(siege_efficiency_values):.3f}")
    
    training_efficiency_values = [m["training_efficiency"] for m in matches if m["training_efficiency"] != float("inf")]
    if training_efficiency_values:
        print(f"  평균 Training Efficiency: {statistics.mean(training_efficiency_values):.1f}턴")
    
    print()
    print("=" * 60)
    print("분석 완료!")
    print("=" * 60)

if __name__ == "__main__":
    main()
