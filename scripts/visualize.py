"""
NYPC 2026 - STEP3 Visualization
P0 그래프만 우선 구현
"""

import json
import csv
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from collections import defaultdict

# 경로 설정
PROJECT_ROOT = Path(__file__).parent.parent
LOGS_ANALYSIS = PROJECT_ROOT / "logs" / "analysis"
FEATURES_CSV = LOGS_ANALYSIS / "features.csv"
OUTPUT_DIR = PROJECT_ROOT / "visualizations"
OUTPUT_DIR.mkdir(exist_ok=True)

# 스타일 설정
sns.set_style("whitegrid")
plt.rcParams["figure.figsize"] = (12, 8)
plt.rcParams["font.size"] = 12

def load_features():
    """features.csv 로드"""
    df = pd.read_csv(FEATURES_CSV)
    # inf 값을 NaN으로 대체
    df = df.replace([np.inf, -np.inf], np.nan)
    return df

def load_all_patterns():
    """모든 경기의 patterns.json 로드"""
    all_patterns = []
    for match_dir in LOGS_ANALYSIS.glob("match_*"):
        patterns_file = match_dir / "patterns.json"
        if patterns_file.exists():
            with open(patterns_file, "r", encoding="utf-8") as f:
                patterns = json.load(f)
                all_patterns.append(patterns)
    return all_patterns

def load_all_map_analysis():
    """모든 경기의 map_analysis.json 로드"""
    all_map_analysis = []
    for match_dir in LOGS_ANALYSIS.glob("match_*"):
        map_file = match_dir / "map_analysis.json"
        if map_file.exists():
            with open(map_file, "r", encoding="utf-8") as f:
                map_analysis = json.load(f)
                all_map_analysis.append(map_analysis)
    return all_map_analysis

def plot_missing_value_matrix(df):
    """P0-1: Missing Value Matrix"""
    plt.figure(figsize=(14, 8))
    sns.heatmap(df.isnull(), cbar=False, cmap="viridis", yticklabels=False)
    plt.title("Missing Value Matrix", fontsize=14)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "01_missing_value_matrix.png")
    plt.close()
    print("✓ Missing Value Matrix saved")

def plot_feature_distributions(df):
    """P0-1: Feature Distributions"""
    # 숫자형 Feature만 선택
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    n_cols = 4
    n_rows = (len(numeric_cols) + n_cols - 1) // n_cols
    
    plt.figure(figsize=(n_cols * 4, n_rows * 3))
    for i, col in enumerate(numeric_cols, 1):
        plt.subplot(n_rows, n_cols, i)
        sns.histplot(df[col].dropna(), kde=True, bins=20)
        plt.title(col, fontsize=10)
        plt.xlabel("")
        plt.ylabel("")
        plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "02_feature_distributions.png", dpi=150)
    plt.close()
    print("✓ Feature Distributions saved")

def plot_correlation_heatmap(df):
    """P0-2: Feature Correlation Heatmap"""
    # 숫자형 Feature만 선택
    numeric_df = df.select_dtypes(include=[np.number])
    corr = numeric_df.corr()
    
    plt.figure(figsize=(14, 12))
    sns.heatmap(corr, annot=True, cmap="coolwarm", center=0, 
                fmt=".2f", square=True, linewidths=0.5, cbar_kws={"shrink": 0.8})
    plt.title("Feature Correlation Heatmap", fontsize=14)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "03_correlation_heatmap.png", dpi=150)
    plt.close()
    print("✓ Correlation Heatmap saved")
    return corr

def plot_opening_timing_scatter(df):
    """P0-3: Opening Timing Scatter"""
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    
    # Scatter 1: first_damage_turn vs total_turns
    sns.scatterplot(data=df, x="first_damage_turn", y="total_turns", 
                    hue="reason", style="reason", s=100, ax=axes[0])
    axes[0].set_title("First Damage Turn vs Total Turns", fontsize=12)
    axes[0].set_xlabel("First Damage Turn")
    axes[0].set_ylabel("Total Turns")
    axes[0].grid(True, alpha=0.3)
    
    # Scatter 2: opening_first_event_turn vs total_turns
    sns.scatterplot(data=df, x="opening_first_event_turn", y="total_turns", 
                    hue="reason", style="reason", s=100, ax=axes[1])
    axes[1].set_title("Opening First Event Turn vs Total Turns", fontsize=12)
    axes[1].set_xlabel("Opening First Event Turn")
    axes[1].set_ylabel("Total Turns")
    axes[1].grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "04_opening_timing_scatter.png", dpi=150)
    plt.close()
    print("✓ Opening Timing Scatter saved")

def plot_combat_time_series(all_patterns):
    """P0-4: Combat Time-Series"""
    max_turn = 200
    
    # 각 턴별 평균 계산
    move_counts = defaultdict(list)
    damage_combat = defaultdict(list)
    siege_counts = defaultdict(list)
    
    for patterns in all_patterns:
        ts = patterns.get("time_series", {})
        for turn in range(1, max_turn + 1):
            turn_str = str(turn)
            move_counts[turn].append(ts.get("move_count", {}).get(turn_str, 0))
            damage_combat[turn].append(ts.get("damage_combat", {}).get(turn_str, 0))
            siege_counts[turn].append(ts.get("siege_count", {}).get(turn_str, 0))
    
    # 평균 계산
    turns = list(range(1, max_turn + 1))
    avg_move = [np.mean(move_counts[t]) for t in turns]
    avg_damage = [np.mean(damage_combat[t]) for t in turns]
    avg_siege = [np.mean(siege_counts[t]) for t in turns]
    
    # Plot
    fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)
    
    axes[0].plot(turns, avg_move, color="blue", linewidth=2)
    axes[0].set_title("Average Move Count per Turn", fontsize=12)
    axes[0].set_ylabel("Move Count")
    axes[0].grid(True, alpha=0.3)
    axes[0].set_xlim(1, 50)  # 초반 50턴만 확대
    
    axes[1].plot(turns, avg_damage, color="red", linewidth=2)
    axes[1].set_title("Average Combat Damage per Turn", fontsize=12)
    axes[1].set_ylabel("Damage")
    axes[1].grid(True, alpha=0.3)
    axes[1].set_xlim(1, 50)
    
    axes[2].plot(turns, avg_siege, color="green", linewidth=2)
    axes[2].set_title("Average Siege Count per Turn", fontsize=12)
    axes[2].set_xlabel("Turn")
    axes[2].set_ylabel("Siege Count")
    axes[2].grid(True, alpha=0.3)
    axes[2].set_xlim(1, 50)
    
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "05_combat_time_series.png", dpi=150)
    plt.close()
    print("✓ Combat Time-Series saved")

def plot_node_visit_heatmap(all_map_analysis):
    """P0-5: Node Visit Heatmap"""
    # 모든 노드의 방문 횟수 합계
    node_visits = defaultdict(int)
    
    for map_analysis in all_map_analysis:
        nv = map_analysis.get("node_visits", {})
        for node, count in nv.items():
            node_visits[int(node)] += count
    
    # DataFrame 생성
    max_node = max(node_visits.keys()) if node_visits else 0
    nodes = list(range(max_node + 1))
    visits = [node_visits.get(node, 0) for node in nodes]
    
    df_visits = pd.DataFrame({
        "node": nodes,
        "visits": visits
    })
    
    # Heatmap (1차원이므로 bar plot으로 표현)
    plt.figure(figsize=(16, 6))
    sns.barplot(data=df_visits, x="node", y="visits", color="skyblue")
    plt.title("Total Node Visits Across All Matches", fontsize=14)
    plt.xlabel("Node ID")
    plt.ylabel("Total Visits")
    plt.xticks(rotation=90, fontsize=8)
    plt.grid(True, alpha=0.3, axis="y")
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "06_node_visit_heatmap.png", dpi=150)
    plt.close()
    print("✓ Node Visit Heatmap saved")

def plot_cluster_visualization(df):
    """P0-6: Cluster Visualization"""
    # 유지 Feature 선택 (이전 설계 기반)
    keep_features = [
        "total_turns", "first_damage_turn", "total_damage_combat", 
        "total_damage_turret", "total_siege_damage", "siege_count", 
        "total_moves", "presumed_dead_count", "opening_has_combat", 
        "opening_has_turret", "opening_has_siege", "opening_first_event_turn"
    ]
    
    # 결측치 처리 (0으로 대체)
    cluster_df = df[keep_features].fillna(0)
    
    # 표준화
    scaler = StandardScaler()
    scaled_data = scaler.fit_transform(cluster_df)
    
    # PCA로 2차원 축소
    pca = PCA(n_components=2)
    pca_data = pca.fit_transform(scaled_data)
    
    # K-Means 클러스터링 (k=2로 시작)
    kmeans = KMeans(n_clusters=2, random_state=42, n_init=10)
    clusters = kmeans.fit_predict(scaled_data)
    
    # 시각화
    plt.figure(figsize=(10, 8))
    scatter = plt.scatter(pca_data[:, 0], pca_data[:, 1], 
                         c=clusters, cmap="viridis", s=100, alpha=0.7)
    plt.colorbar(scatter, label="Cluster")
    plt.title(f"Cluster Visualization (k=2, PCA: {pca.explained_variance_ratio_.sum():.2%} variance)", 
              fontsize=14)
    plt.xlabel(f"PC1 ({pca.explained_variance_ratio_[0]:.2%})")
    plt.ylabel(f"PC2 ({pca.explained_variance_ratio_[1]:.2%})")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "07_cluster_visualization.png", dpi=150)
    plt.close()
    
    # 클러스터별 Feature 평균
    df["cluster"] = clusters
    cluster_means = df.groupby("cluster")[keep_features].mean()
    cluster_means.to_csv(OUTPUT_DIR / "cluster_means.csv")
    print("✓ Cluster Visualization saved")
    return clusters, cluster_means

def main():
    print("=" * 60)
    print("NYPC 2026 STEP3 - Visualization")
    print("=" * 60)
    
    # 1. 데이터 로드
    print("\n[1/7] Loading data...")
    df = load_features()
    all_patterns = load_all_patterns()
    all_map_analysis = load_all_map_analysis()
    print(f"✓ Loaded {len(df)} matches")
    
    # 2. P0-1: Missing Value Matrix
    print("\n[2/7] Plotting Missing Value Matrix...")
    plot_missing_value_matrix(df)
    
    # 3. P0-1: Feature Distributions
    print("\n[3/7] Plotting Feature Distributions...")
    plot_feature_distributions(df)
    
    # 4. P0-2: Correlation Heatmap
    print("\n[4/7] Plotting Correlation Heatmap...")
    corr = plot_correlation_heatmap(df)
    
    # 5. P0-3: Opening Timing Scatter
    print("\n[5/7] Plotting Opening Timing Scatter...")
    plot_opening_timing_scatter(df)
    
    # 6. P0-4: Combat Time-Series
    print("\n[6/7] Plotting Combat Time-Series...")
    plot_combat_time_series(all_patterns)
    
    # 7. P0-5: Node Visit Heatmap
    print("\n[7/7] Plotting Node Visit Heatmap...")
    plot_node_visit_heatmap(all_map_analysis)
    
    # 8. P0-6: Cluster Visualization
    print("\n[8/8] Plotting Cluster Visualization...")
    clusters, cluster_means = plot_cluster_visualization(df)
    
    print("\n" + "=" * 60)
    print(f"✓ All visualizations saved to {OUTPUT_DIR}")
    print("=" * 60)
    
    # Feature Quality Audit 결과 저장
    print("\n--- Feature Quality Audit ---")
    print(f"Total Features: {len(df.columns)}")
    print(f"Missing Values:")
    print(df.isnull().sum()[df.isnull().sum() > 0])
    
    return df, corr, clusters, cluster_means

if __name__ == "__main__":
    main()