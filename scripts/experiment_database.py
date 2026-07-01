#!/usr/bin/env python3
"""
NYPC 2026 - Experiment Database Manager
모든 Weight Sweep 결과를 영구적으로 누적 저장합니다.

사용법:
  python scripts/experiment_database.py                    # DB 초기화
  python scripts/experiment_database.py --import STEP6D   # STEP6D 결과 import
  python scripts/experiment_database.py --import STEP6E   # STEP6E 결과 import
  python scripts/experiment_database.py --report          # 전체 Report
  python scripts/experiment_database.py --export CSV     # CSV export
"""

import os
import sys
import csv
import json
import glob
import argparse
from pathlib import Path
from datetime import datetime
from collections import defaultdict

PROJECT_ROOT = Path(__file__).parent.parent
DB_DIR = PROJECT_ROOT / "logs" / "experiment_database"
DB_CSV = DB_DIR / "experiments.csv"
DB_META = DB_DIR / "meta.json"

# DB Schema
DB_FIELDS = [
    # Meta
    "experiment_id", "timestamp", "step", "git_commit",
    # Match Type (NEW)
    "match_type",  # "self_play" or "cross"
    "left_profile",  # LEFT AI Profile ID (NEW)
    "right_profile",  # RIGHT AI Profile ID (NEW)
    "cross_result",  # WIN/DRAW/LOSE from LEFT perspective (NEW)
    # Weight Info
    "weight_name", "weight_value",
    # Match Result
    "match_count", "win", "draw", "lose", "win_rate_pct", "draw_rate_pct", "lose_rate_pct",
    # Behavior Distribution
    "behavior_move_pct", "behavior_train_pct", "behavior_upgrade_pct", "behavior_wait_pct",
    "behavior_move_count", "behavior_train_count", "behavior_upgrade_count", "behavior_wait_count",
    # Movement Metrics
    "avg_moves_per_turn", "move_select_rate", "first_move_turn", "avg_move_distance", "avg_hq_approach",
    # Stronghold Metrics
    "strongholds_visit_count", "first_stronghold_visit", "stronghold_occupied_turns", "stronghold_capture_count",
    # Upgrade Metrics
    "upgrade_candidate_count", "upgrade_select_count", "first_upgrade_turn", "base_construction_count",
    # Training Metrics
    "train_select_count", "avg_train_n",
    # HQ Metrics
    "avg_hq_distance", "min_hq_distance", "hq_adjacent_count", "hq_attack_count",
    # Region Metrics
    "unique_regions_visited",
    # Score Metrics
    "avg_top1_score", "avg_top2_score", "avg_top1_top2_gap",
    "final_score_mean", "final_score_std", "final_score_min", "final_score_max",
    # Gold Metrics
    "gold_start", "gold_end", "gold_min", "gold_max", "avg_gold", "avg_income", "avg_upkeep",
    # Action Rank Distribution
    "avg_action_rank", "min_action_rank", "max_action_rank", "total_candidates_considered",
    # Contribution Distribution
    "contrib_move_cost_mean", "contrib_train_n_mean", "contrib_turns_to_enemy_hq_mean",
    "contrib_remaining_gold_mean", "contrib_train_cost_mean",
    "top_dominance_feature", "top_dominance_pct",
    # Execution Info
    "elapsed_sec", "log_dir",
    # Additional
    "early_stopped", "adaptive_decisions"
]


def init_db():
    """DB 디렉토리 및 CSV 파일 초기화"""
    DB_DIR.mkdir(parents=True, exist_ok=True)

    if not DB_CSV.exists():
        with open(DB_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=DB_FIELDS)
            writer.writeheader()
        print(f"[INIT] Experiment DB created: {DB_CSV}")

    # Meta 파일 초기화
    if not DB_META.exists():
        meta = {
            "created": datetime.now().isoformat(),
            "last_id": 0,
            "experiments": []
        }
        with open(DB_META, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)
        print(f"[INIT] Meta file created: {DB_META}")


def get_next_id():
    """다음 Experiment ID 가져오기"""
    if DB_META.exists():
        with open(DB_META, "r", encoding="utf-8") as f:
            meta = json.load(f)
        next_id = meta.get("last_id", 0) + 1
    else:
        next_id = 1
    return next_id


def update_meta(experiment_id, step, weight_name, weight_value):
    """Meta 파일 업데이트"""
    if DB_META.exists():
        with open(DB_META, "r", encoding="utf-8") as f:
            meta = json.load(f)
    else:
        meta = {"created": datetime.now().isoformat(), "last_id": 0, "experiments": []}

    meta["last_id"] = experiment_id
    meta["experiments"].append({
        "id": experiment_id,
        "step": step,
        "weight_name": weight_name,
        "weight_value": weight_value,
        "timestamp": datetime.now().isoformat()
    })

    with open(DB_META, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)


def import_from_summary_csv(csv_path, step, git_commit="unknown"):
    """behavior_summary.csv에서 데이터 import"""
    if not csv_path.exists():
        print(f"[ERROR] CSV not found: {csv_path}")
        return 0

    init_db()
    imported = 0
    next_id = get_next_id()

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            exp_id = next_id
            next_id += 1

            # 기본 데이터 구성
            record = {
                "experiment_id": exp_id,
                "timestamp": datetime.now().isoformat(),
                "step": step,
                "git_commit": git_commit,
                # Weight Info
                "weight_name": row.get("weight_name", ""),
                "weight_value": row.get("weight_value", ""),
                # Match Result
                "match_count": int(float(row.get("match_count", 0))),
                "win": int(float(row.get("win", 0))),
                "draw": int(float(row.get("draw", 0))),
                "lose": int(float(row.get("lose", 0))),
                "win_rate_pct": float_or_default(row.get("win_rate_pct", 0)),
                "draw_rate_pct": float_or_default(row.get("draw_rate_pct", 0)),
                "lose_rate_pct": float_or_default(row.get("lose_rate_pct", 0)),
                # Behavior Distribution
                "behavior_move_pct": float_or_default(row.get("behavior_move_pct", 0)),
                "behavior_train_pct": float_or_default(row.get("behavior_train_pct", 0)),
                "behavior_upgrade_pct": float_or_default(row.get("behavior_upgrade_pct", 0)),
                "behavior_wait_pct": float_or_default(row.get("behavior_wait_pct", 0)),
                "behavior_move_count": int(float(row.get("behavior_move_count", 0))),
                "behavior_train_count": int(float(row.get("behavior_train_count", 0))),
                "behavior_upgrade_count": int(float(row.get("behavior_upgrade_count", 0))),
                "behavior_wait_count": int(float(row.get("behavior_wait_count", 0))),
                # Movement Metrics
                "avg_moves_per_turn": float_or_default(row.get("avg_moves_per_turn")),
                "move_select_rate": float_or_default(row.get("move_select_rate")),
                "first_move_turn": str_or_default(row.get("first_move_turn")),
                "avg_move_distance": float_or_default(row.get("avg_move_distance")),
                "avg_hq_approach": float_or_default(row.get("avg_hq_approach")),
                # Stronghold Metrics
                "strongholds_visit_count": int(float(row.get("strongholds_visit_count", 0))),
                "first_stronghold_visit": str_or_default(row.get("first_stronghold_visit")),
                "stronghold_occupied_turns": int(float(row.get("stronghold_occupied_turns", 0))),
                "stronghold_capture_count": int(float(row.get("stronghold_capture_count", 0))),
                # Upgrade Metrics
                "upgrade_candidate_count": int(float(row.get("upgrade_candidate_count", 0))),
                "upgrade_select_count": int(float(row.get("upgrade_select_count", 0))),
                "first_upgrade_turn": str_or_default(row.get("first_upgrade_turn")),
                "base_construction_count": int(float(row.get("base_construction_count", 0))),
                # Training Metrics
                "train_select_count": int(float(row.get("train_select_count", 0))),
                "avg_train_n": float_or_default(row.get("avg_train_n")),
                # HQ Metrics
                "avg_hq_distance": float_or_default(row.get("avg_hq_distance")),
                "min_hq_distance": int(float(row.get("min_hq_distance", 0))),
                "hq_adjacent_count": int(float(row.get("hq_adjacent_count", 0))),
                "hq_attack_count": int(float(row.get("hq_attack_count", 0))),
                # Region Metrics
                "unique_regions_visited": int(float(row.get("unique_regions_visited", 0))),
                # Score Metrics
                "avg_top1_score": float_or_default(row.get("avg_top1_score")),
                "avg_top2_score": float_or_default(row.get("avg_top2_score")),
                "avg_top1_top2_gap": float_or_default(row.get("avg_top1_top2_gap")),
                "final_score_mean": float_or_default(row.get("final_score_mean")),
                "final_score_std": float_or_default(row.get("final_score_std")),
                "final_score_min": float_or_default(row.get("final_score_min")),
                "final_score_max": float_or_default(row.get("final_score_max")),
                # Gold Metrics
                "gold_start": int(float(row.get("gold_start", 0))),
                "gold_end": int(float(row.get("gold_end", 0))),
                "gold_min": int(float(row.get("gold_min", 0))),
                "gold_max": int(float(row.get("gold_max", 0))),
                "avg_gold": float_or_default(row.get("avg_gold")),
                "avg_income": float_or_default(row.get("avg_income")),
                "avg_upkeep": float_or_default(row.get("avg_upkeep")),
                # Action Rank Distribution
                "avg_action_rank": float_or_default(row.get("avg_action_rank")),
                "min_action_rank": int(float(row.get("min_action_rank", 999))),
                "max_action_rank": int(float(row.get("max_action_rank", 0))),
                "total_candidates_considered": int(float(row.get("total_candidates_considered", 0))),
                # Contribution Distribution
                "contrib_move_cost_mean": float_or_default(row.get("contrib_move_cost_mean")),
                "contrib_train_n_mean": float_or_default(row.get("contrib_train_n_mean")),
                "contrib_turns_to_enemy_hq_mean": float_or_default(row.get("contrib_turns_to_enemy_hq_mean")),
                "contrib_remaining_gold_mean": float_or_default(row.get("contrib_remaining_gold_mean")),
                "contrib_train_cost_mean": float_or_default(row.get("contrib_train_cost_mean")),
                "top_dominance_feature": row.get("top_dominance_feature", ""),
                "top_dominance_pct": float_or_default(row.get("top_dominance_pct")),
                # Execution Info
                "elapsed_sec": float_or_default(row.get("elapsed_sec", 0)),
                "log_dir": row.get("log_dir", ""),
                # Additional
                "early_stopped": row.get("early_stopped", "False"),
                "adaptive_decisions": row.get("adaptive_decisions", "[]")
            }

            # CSV에 Append
            with open(DB_CSV, "a", newline="", encoding="utf-8") as cf:
                writer = csv.DictWriter(cf, fieldnames=DB_FIELDS)
                writer.writerow(record)

            # Meta 업데이트
            update_meta(exp_id, step, record["weight_name"], record["weight_value"])
            imported += 1

    print(f"[IMPORT] {imported} records imported from {csv_path}")
    return imported


def float_or_default(val, default=0.0):
    """문자열을 float로 변환, 실패시 기본값"""
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def str_or_default(val, default=""):
    """값이 없거나 'N/A'면 빈 문자열 반환"""
    if val is None or val == "N/A" or val == "":
        return default
    return str(val)


def generate_report():
    """전체 Experiment Report 생성"""
    if not DB_CSV.exists():
        print("[ERROR] No experiment database found. Run with --import first.")
        return

    # 데이터 로드
    experiments = []
    with open(DB_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            experiments.append(row)

    if not experiments:
        print("[ERROR] No experiments in database.")
        return

    print("=" * 80)
    print("NYPC 2026 - Experiment Database Report")
    print("=" * 80)
    print(f"Total Experiments: {len(experiments)}")
    print(f"DB Location: {DB_CSV}")
    print()

    # STEP별 분류
    by_step = defaultdict(list)
    for exp in experiments:
        by_step[exp["step"]].append(exp)

    for step, exps in sorted(by_step.items()):
        print(f"\n{'='*40}")
        print(f"STEP: {step} ({len(exps)} experiments)")
        print(f"{'='*40}")

        # Weight별 정렬
        by_weight = defaultdict(list)
        for exp in exps:
            by_weight[(exp["weight_name"], exp["weight_value"])].append(exp)

        for (wn, wv), exps in sorted(by_weight.items()):
            print(f"\n  {wn}={wv}:")
            for exp in exps:
                win_rate = float(exp.get("win_rate_pct", 0))
                draw_rate = float(exp.get("draw_rate_pct", 0))
                move_pct = float(exp.get("behavior_move_pct", 0))
                print(f"    ID={exp['experiment_id']}: "
                      f"Win={win_rate:.1f}%, Draw={draw_rate:.1f}%, "
                      f"MOVE={move_pct:.1f}%, Match={exp['match_count']}")


def export_csv(output_path=None):
    """전체 DB를 CSV로 export"""
    if not DB_CSV.exists():
        print("[ERROR] No experiment database found.")
        return

    if output_path is None:
        output_path = DB_DIR / f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    import shutil
    shutil.copy(DB_CSV, output_path)
    print(f"[EXPORT] Exported to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="NYPC 2026 Experiment Database Manager")
    parser.add_argument("--init", action="store_true", help="Initialize DB")
    parser.add_argument("--import", dest="import_step", type=str, help="Import from step (e.g., STEP6D)")
    parser.add_argument("--report", action="store_true", help="Generate report")
    parser.add_argument("--export", nargs="?", const="default", type=str, help="Export to CSV")
    args = parser.parse_args()

    if args.init:
        init_db()
    elif args.import_step:
        # STEP6D, STEP6E 등
        step = args.import_step
        csv_path = PROJECT_ROOT / "logs" / f"weight_sweep_{step.lower()}" / "report" / "behavior_summary.csv"
        git_commit = "unknown"
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                git_commit = result.stdout.strip()
        except:
            pass
        import_from_summary_csv(csv_path, step, git_commit)
    elif args.report:
        generate_report()
    elif args.export is not None:
        if args.export == "default":
            export_csv()
        else:
            export_csv(Path(args.export))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
