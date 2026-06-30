"""
NYPC 2026 STEP3 - Correlation Analysis
실제 데이터 기반으로 Feature 상관관계 분석
"""

import numpy as np
import pandas as pd
from pathlib import Path

# 경로 설정
PROJECT_ROOT = Path(__file__).parent.parent
LOGS_ANALYSIS = PROJECT_ROOT / "logs" / "analysis"
FEATURES_CSV = LOGS_ANALYSIS / "features.csv"
OUTPUT_DIR = PROJECT_ROOT / "visualizations"
OUTPUT_DIR.mkdir(exist_ok=True)

def main():
    print("=" * 60)
    print("NYPC 2026 STEP3 - Correlation Analysis")
    print("=" * 60)
    
    # 데이터 로드
    df = pd.read_csv(FEATURES_CSV)
    df = df.replace([np.inf, -np.inf], np.nan)
    
    # 유지 Feature만 선택
    keep_features = [
        "total_turns", "first_damage_turn", "first_combat_turn",
        "total_damage_combat", "total_damage_turret", "total_siege_damage",
        "siege_count", "total_moves", "presumed_dead_count",
        "opening_has_combat", "opening_has_turret", "opening_has_siege",
        "opening_first_event_turn"
    ]
    
    # 숫자형 Feature만
    numeric_features = [f for f in keep_features if pd.api.types.is_numeric_dtype(df[f])]
    corr_df = df[numeric_features].corr()
    
    # 결과 저장
    corr_df.to_csv(OUTPUT_DIR / "correlation_matrix.csv", encoding="utf-8-sig")
    
    # 강한 상관관계 (|r| >= 0.7)
    print("\n--- Strong Correlations (|r| >= 0.7) ---")
    strong_corr = []
    for i in range(len(corr_df.columns)):
        for j in range(i+1, len(corr_df.columns)):
            corr_val = corr_df.iloc[i, j]
            if abs(corr_val) >= 0.7:
                strong_corr.append({
                    "feature1": corr_df.columns[i],
                    "feature2": corr_df.columns[j],
                    "correlation": corr_val
                })
    
    if strong_corr:
        strong_df = pd.DataFrame(strong_corr)
        strong_df = strong_df.sort_values("correlation", key=abs, ascending=False)
        print(strong_df.to_string(index=False))
    else:
        print("No strong correlations found")
    
    # 중간 상관관계 (0.5 <= |r| < 0.7)
    print("\n--- Moderate Correlations (0.5 <= |r| < 0.7) ---")
    moderate_corr = []
    for i in range(len(corr_df.columns)):
        for j in range(i+1, len(corr_df.columns)):
            corr_val = corr_df.iloc[i, j]
            if 0.5 <= abs(corr_val) < 0.7:
                moderate_corr.append({
                    "feature1": corr_df.columns[i],
                    "feature2": corr_df.columns[j],
                    "correlation": corr_val
                })
    
    if moderate_corr:
        moderate_df = pd.DataFrame(moderate_corr)
        moderate_df = moderate_df.sort_values("correlation", key=abs, ascending=False)
        print(moderate_df.to_string(index=False))
    else:
        print("No moderate correlations found")
    
    print("\n" + "=" * 60)
    print(f"✓ Correlation matrix saved to {OUTPUT_DIR / 'correlation_matrix.csv'}")
    print("=" * 60)
    
    return corr_df

if __name__ == "__main__":
    main()