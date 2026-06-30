"""
NYPC 2026 STEP3 - Feature Engineering
실제 데이터 기반으로 새로운 Feature 생성
"""

import json
import numpy as np
import pandas as pd
from pathlib import Path
from collections import defaultdict

# 경로 설정
PROJECT_ROOT = Path(__file__).parent.parent
LOGS_ANALYSIS = PROJECT_ROOT / "logs" / "analysis"
FEATURES_CSV = LOGS_ANALYSIS / "features.csv"
OUTPUT_DIR = PROJECT_ROOT / "visualizations"
OUTPUT_DIR.mkdir(exist_ok=True)

def load_patterns(match_id):
    """단일 경기의 patterns.json 로드"""
    patterns_file = LOGS_ANALYSIS / f"match_{match_id:04d}" / "patterns.json"
    if patterns_file.exists():
        with open(patterns_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

def load_map_analysis(match_id):
    """단일 경기의 map_analysis.json 로드"""
    map_file = LOGS_ANALYSIS / f"match_{match_id:04d}" / "map_analysis.json"
    if map_file.exists():
        with open(map_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

def load_warrior_tracks(match_id):
    """단일 경기의 warrior_tracks.json 로드"""
    tracks_file = LOGS_ANALYSIS / f"match_{match_id:04d}" / "warrior_tracks.json"
    if tracks_file.exists():
        with open(tracks_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

def main():
    print("=" * 60)
    print("NYPC 2026 STEP3 - Feature Engineering")
    print("=" * 60)
    
    # 기존 데이터 로드
    df = pd.read_csv(FEATURES_CSV)
    df = df.replace([np.inf, -np.inf], np.nan)
    
    # 새로운 Feature 저장소
    new_features = []
    
    print("\n--- Generating New Features ---")
    
    for idx, row in df.iterrows():
        match_id = int(row["match_id"])
        
        # 패턴, 맵 분석, 전사 트랙 로드
        patterns = load_patterns(match_id)
        map_analysis = load_map_analysis(match_id)
        warrior_tracks = load_warrior_tracks(match_id)
        
        feat = {"match_id": match_id}
        
        # 1. Early Move Count (1-6턴)
        if patterns and "time_series" in patterns:
            move_counts = patterns["time_series"].get("move_count", {})
            early_moves = sum(move_counts.get(str(t), 0) for t in range(1, 7))
            feat["early_move_count"] = early_moves
        else:
            feat["early_move_count"] = 0
        
        # 2. Early Damage (1-12턴)
        if patterns and "time_series" in patterns:
            damage_combat = patterns["time_series"].get("damage_combat", {})
            early_damage = sum(damage_combat.get(str(t), 0) for t in range(1, 13))
            feat["early_damage"] = early_damage
        else:
            feat["early_damage"] = 0
        
        # 3. Total Node Visits
        if map_analysis and "node_visits" in map_analysis:
            total_node_visits = sum(map_analysis["node_visits"].values())
            feat["total_node_visits"] = total_node_visits
        else:
            feat["total_node_visits"] = 0
        
        # 4. Stronghold Visits
        if map_analysis and "stronghold_visits" in map_analysis:
            total_stronghold_visits = sum(map_analysis["stronghold_visits"].values())
            feat["total_stronghold_visits"] = total_stronghold_visits
        else:
            feat["total_stronghold_visits"] = 0
        
        # 5. Combat Peak Turn (가장 많은 데미지가 발생한 턴)
        if patterns and "time_series" in patterns:
            damage_combat = patterns["time_series"].get("damage_combat", {})
            if damage_combat:
                # (damage, turn) 튜플 리스트로 변환
                damage_list = [(int(dmg), int(t)) for t, dmg in damage_combat.items()]
                if damage_list:
                    damage_list.sort(reverse=True, key=lambda x: x[0])
                    feat["combat_peak_turn"] = damage_list[0][1]
                else:
                    feat["combat_peak_turn"] = 0
            else:
                feat["combat_peak_turn"] = 0
        else:
            feat["combat_peak_turn"] = 0
        
        # 6. Move Peak Turn
        if patterns and "time_series" in patterns:
            move_counts = patterns["time_series"].get("move_count", {})
            if move_counts:
                move_list = [(int(cnt), int(t)) for t, cnt in move_counts.items()]
                if move_list:
                    move_list.sort(reverse=True, key=lambda x: x[0])
                    feat["move_peak_turn"] = move_list[0][1]
                else:
                    feat["move_peak_turn"] = 0
            else:
                feat["move_peak_turn"] = 0
        else:
            feat["move_peak_turn"] = 0
        
        # 7. Average Warrior Last Seen Turn
        if warrior_tracks:
            last_seen_turns = []
            for warrior_id, track in warrior_tracks.items():
                if "last_seen_turn" in track:
                    last_seen_turns.append(track["last_seen_turn"])
            if last_seen_turns:
                feat["avg_warrior_last_seen_turn"] = np.mean(last_seen_turns)
            else:
                feat["avg_warrior_last_seen_turn"] = 0
        else:
            feat["avg_warrior_last_seen_turn"] = 0
        
        # 8. Total Damage (combat + turret)
        feat["total_damage"] = row["total_damage_combat"] + row["total_damage_turret"]
        
        # 9. Combat Ratio (combat damage / total damage)
        total_damage = row["total_damage_combat"] + row["total_damage_turret"]
        if total_damage > 0:
            feat["combat_ratio"] = row["total_damage_combat"] / total_damage
        else:
            feat["combat_ratio"] = 0
        
        # 10. Aggression Score (early damage + early moves)
        feat["aggression_score"] = feat["early_damage"] + feat["early_move_count"]
        
        new_features.append(feat)
    
    # 새로운 Feature DataFrame
    new_feat_df = pd.DataFrame(new_features)
    
    # 기존 데이터와 병합
    final_df = pd.merge(df, new_feat_df, on="match_id", how="left")
    
    # 저장
    final_df.to_csv(OUTPUT_DIR / "features_with_new.csv", index=False, encoding="utf-8-sig")
    
    # 새로운 Feature 목록 출력
    new_feature_names = [col for col in new_feat_df.columns if col != "match_id"]
    print(f"\n--- New Features Generated ({len(new_feature_names)}) ---")
    for feat_name in new_feature_names:
        print(f"  - {feat_name}")
    
    # Feature 평가
    print("\n--- New Feature Summary ---")
    summary = new_feat_df.describe()
    print(summary.to_string())
    
    print("\n" + "=" * 60)
    print(f"✓ New features saved to {OUTPUT_DIR / 'features_with_new.csv'}")
    print("=" * 60)
    
    return final_df, new_feature_names

if __name__ == "__main__":
    main()