"""
NYPC 2026 STEP3 - Feature Quality Audit
실제 데이터 기반으로 Feature 평가
"""

import json
import csv
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
    print("NYPC 2026 STEP3 - Feature Quality Audit")
    print("=" * 60)
    
    # 데이터 로드
    df = pd.read_csv(FEATURES_CSV)
    df = df.replace([np.inf, -np.inf], np.nan)
    
    # Feature Quality Audit 결과 저장
    audit_results = []
    
    for col in df.columns:
        # 기본 통계
        missing_count = df[col].isnull().sum()
        missing_rate = missing_count / len(df)
        unique_count = df[col].nunique()
        is_numeric = pd.api.types.is_numeric_dtype(df[col])
        
        # Variance (숫자형만)
        variance = df[col].var() if is_numeric else np.nan
        
        # Constant 여부
        is_constant = (unique_count <= 1)
        
        # Sparse 여부 (결측치 50% 이상)
        is_sparse = (missing_rate >= 0.5)
        
        # Derived 여부 (이름으로 판단)
        derived_keywords = ["avg", "per", "ratio", "rate", "efficiency", "risk", "index"]
        is_derived = any(keyword in col.lower() for keyword in derived_keywords)
        
        # Identifier 여부
        is_identifier = (col == "match_id")
        
        # 삭제 이유 카테고리
        delete_reason = ""
        if is_identifier:
            delete_reason = "Identifier"
        elif is_constant:
            delete_reason = "Constant"
        elif missing_rate == 1.0:
            delete_reason = "Always Missing"
        elif is_sparse:
            delete_reason = "Sparse"
        elif is_derived:
            delete_reason = "Derived"
        
        audit_results.append({
            "feature": col,
            "missing_count": missing_count,
            "missing_rate": f"{missing_rate:.1%}",
            "unique_count": unique_count,
            "variance": variance,
            "is_constant": is_constant,
            "is_sparse": is_sparse,
            "is_derived": is_derived,
            "is_identifier": is_identifier,
            "delete_reason": delete_reason
        })
    
    # DataFrame으로 변환
    audit_df = pd.DataFrame(audit_results)
    audit_df = audit_df.sort_values("delete_reason", ascending=False)
    
    # 결과 저장
    audit_df.to_csv(OUTPUT_DIR / "feature_quality_audit.csv", index=False, encoding="utf-8-sig")
    
    # 결과 출력
    print("\n--- Feature Quality Audit Results ---")
    print(audit_df.to_string(index=False))
    
    # 삭제 후보 Feature
    delete_candidates = audit_df[audit_df["delete_reason"] != ""]["feature"].tolist()
    print(f"\n--- Delete Candidates ({len(delete_candidates)}) ---")
    for feat in delete_candidates:
        reason = audit_df[audit_df["feature"] == feat]["delete_reason"].iloc[0]
        print(f"  - {feat}: {reason}")
    
    # 유지 Feature
    keep_features = audit_df[audit_df["delete_reason"] == ""]["feature"].tolist()
    print(f"\n--- Keep Features ({len(keep_features)}) ---")
    for feat in keep_features:
        print(f"  - {feat}")
    
    print("\n" + "=" * 60)
    print(f"✓ Audit results saved to {OUTPUT_DIR / 'feature_quality_audit.csv'}")
    print("=" * 60)
    
    return audit_df, df

if __name__ == "__main__":
    main()