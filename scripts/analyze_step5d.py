#!/usr/bin/env python3
"""
NYPC 2026 STEP 5D - Evaluation Benchmark & Analysis
Analyzes the new evaluation function logs
"""

import json
from pathlib import Path
from collections import defaultdict, Counter
import statistics
import math


def parse_log(log_path: Path):
    """Parse a single log file and collect analysis data"""
    data = {
        "match_summary": {},
        "action_distribution": defaultdict(int),
        "action_distribution_by_turn": defaultdict(lambda: defaultdict(int)),
        "feature_values": defaultdict(list),
        "contribution_values": defaultdict(list),
        "final_scores": [],
        "score_separations": [],
        "turns": 0
    }

    with open(log_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Find match result
    for line in lines:
        if line.startswith("RESULT"):
            parts = line.split()
            data["match_summary"]["winner"] = parts[1]
            data["match_summary"]["reason"] = parts[2]
            break

    # Process each turn
    current_turn = None
    for line in lines:
        if line.startswith("TURN ") and "RESULT" not in line:
            current_turn = int(line.split()[1])
            data["turns"] = max(data["turns"], current_turn)

        # Parse debug lines
        if line.startswith("# Debug "):
            # Extract JSON part
            json_str = line[len("# Debug LEFT: "):] if "LEFT" in line else line[len("# Debug RIGHT: "):]
            try:
                debug_data = json.loads(json_str)

                # Feature dump (type: move/train/upgrade)
                if "type" in debug_data and "feature_dump" in debug_data:
                    ftype = debug_data["type"]
                    features = debug_data["feature_dump"]
                    for k, v in features.items():
                        key = f"{ftype}_{k}"
                        data["feature_values"][key].append(v)
                        data["feature_values"][k].append(v)  # Also aggregate by feature name

                # Contribution dump
                if "contribution_dump" in debug_data:
                    contributions = debug_data["contribution_dump"]
                    for k, v in contributions.items():
                        data["contribution_values"][k].append(v)
                        data["contribution_values"]["all"].append(v)  # All contributions

                # Candidates and score distribution
                if "candidates" in debug_data and "final_score_distribution" in debug_data:
                    candidates = debug_data["candidates"]
                    fsd = debug_data["final_score_distribution"]

                    # Collect all scores for this turn
                    scores = [c["score"] for c in candidates if c["affordable"]]
                    if scores:
                        scores_sorted = sorted(scores, reverse=True)
                        data["final_scores"].extend(scores)

                        # Score separation metrics
                        if len(scores_sorted) >= 2:
                            data["score_separations"].append({
                                "top1_top2": scores_sorted[0] - scores_sorted[1],
                                "top2_top3": scores_sorted[1] - scores_sorted[2] if len(scores_sorted) >=3 else None,
                                "top1_mean": scores_sorted[0] - statistics.mean(scores),
                                "top1_worst": scores_sorted[0] - scores_sorted[-1],
                                "mean_gap": statistics.mean([scores_sorted[i] - scores_sorted[i+1] for i in range(len(scores_sorted)-1)]),
                                "median_gap": statistics.median([scores_sorted[i] - scores_sorted[i+1] for i in range(len(scores_sorted)-1)]),
                            })

                    # Action distribution
                    for candidate in candidates:
                        if candidate.get("train_n", 0) > 0:
                            data["action_distribution"]["TRAIN"] += 1
                            data["action_distribution_by_turn"][current_turn]["TRAIN"] +=1
                        if candidate.get("moves", []):
                            data["action_distribution"]["MOVE"] +=1
                            data["action_distribution_by_turn"][current_turn]["MOVE"] +=1
                        if candidate.get("upgrades", []):
                            data["action_distribution"]["UPGRADE"] +=1
                            data["action_distribution_by_turn"][current_turn]["UPGRADE"] +=1
                        if not candidate.get("train_n",0) and not candidate.get("moves",[]) and not candidate.get("upgrades",[]):
                            data["action_distribution"]["WAIT"] +=1
                            data["action_distribution_by_turn"][current_turn]["WAIT"] +=1

            except json.JSONDecodeError:
                pass  # Skip non-JSON debug lines

    return data


def analyze_all_logs(log_dir: Path):
    """Analyze all log files in the directory"""
    all_data = {
        "match_summaries": [],
        "total_action_distribution": defaultdict(int),
        "all_feature_values": defaultdict(list),
        "all_contribution_values": defaultdict(list),
        "all_final_scores": [],
        "all_score_separations": []
    }

    log_files = sorted(log_dir.glob("*.log"))
    print(f"Found {len(log_files)} log files")

    for log_file in log_files:
        print(f"Analyzing {log_file.name}...")
        log_data = parse_log(log_file)

        if log_data["match_summary"]:
            all_data["match_summaries"].append(log_data["match_summary"])

        for k, v in log_data["action_distribution"].items():
            all_data["total_action_distribution"][k] += v

        for k, v in log_data["feature_values"].items():
            all_data["all_feature_values"][k].extend(v)

        for k, v in log_data["contribution_values"].items():
            all_data["all_contribution_values"][k].extend(v)

        all_data["all_final_scores"].extend(log_data["final_scores"])
        all_data["all_score_separations"].extend(log_data["score_separations"])

    return all_data


def print_statistics(name, values):
    """Print statistics for a list of values"""
    if not values:
        print(f"  {name}: No data")
        return

    mean = statistics.mean(values)
    stdev = statistics.stdev(values) if len(values) > 1 else 0
    min_val = min(values)
    max_val = max(values)
    q1 = statistics.quantiles(values, n=4)[0]
    median = statistics.median(values)
    q3 = statistics.quantiles(values, n=4)[2]

    print(f"  {name}:")
    print(f"    Mean: {mean:.4f}")
    print(f"    StdDev: {stdev:.4f}")
    print(f"    Min: {min_val:.4f}")
    print(f"    Q1: {q1:.4f}")
    print(f"    Median: {median:.4f}")
    print(f"    Q3: {q3:.4f}")
    print(f"    Max: {max_val:.4f}")


def main():
    log_dir = Path("logs/baseline_benchmark")
    all_data = analyze_all_logs(log_dir)

    print("\n" + "="*80)
    print("1. Match Summary")
    print("="*80)
    total_matches = len(all_data["match_summaries"])
    print(f"Total Matches: {total_matches}")

    winner_counts = Counter()
    reason_counts = Counter()
    for match in all_data["match_summaries"]:
        winner_counts[match.get("winner", "UNKNOWN")] +=1
        reason_counts[match.get("reason", "UNKNOWN")] +=1

    print(f"Winners: {dict(winner_counts)}")
    print(f"Reasons: {dict(reason_counts)}")

    print("\n" + "="*80)
    print("2. Action Distribution")
    print("="*80)
    total_actions = sum(all_data["total_action_distribution"].values())
    for action, count in all_data["total_action_distribution"].items():
        percentage = (count / total_actions) * 100
        print(f"  {action}: {count} ({percentage:.2f}%)")

    print("\n" + "="*80)
    print("3. Feature Distribution")
    print("="*80)
    for feature in sorted(all_data["all_feature_values"].keys()):
        if feature != "all":
            print_statistics(feature, all_data["all_feature_values"][feature])

    print("\n" + "="*80)
    print("4. Contribution Distribution")
    print("="*80)
    for contrib in sorted(all_data["all_contribution_values"].keys()):
        if contrib != "all":
            print_statistics(contrib, all_data["all_contribution_values"][contrib])

    # Mean absolute contribution
    all_contrib_abs = [abs(x) for x in all_data["all_contribution_values"]["all"]]
    print_statistics("Mean Absolute Contribution (all)", all_contrib_abs)

    print("\n" + "="*80)
    print("5. Dominance Analysis")
    print("="*80)
    contrib_means = {}
    for contrib in all_data["all_contribution_values"].keys():
        if contrib != "all" and all_data["all_contribution_values"][contrib]:
            contrib_means[contrib] = statistics.mean([abs(x) for x in all_data["all_contribution_values"][contrib]])

    total_mean = sum(contrib_means.values()) if contrib_means else 1
    for contrib, mean_abs in sorted(contrib_means.items(), key=lambda x: -x[1]):
        percentage = (mean_abs / total_mean) * 100
        print(f"  {contrib}: {mean_abs:.4f} ({percentage:.2f}%)")
        if percentage > 50:
            print(f"    WARNING: This feature dominates the evaluation!")

    print("\n" + "="*80)
    print("6. Final Score Distribution & Separation")
    print("="*80)
    print_statistics("Final Scores", all_data["all_final_scores"])

    # Analyze score separations
    if all_data["all_score_separations"]:
        print("\n  Score Separation Metrics:")
        for metric in ["top1_top2", "top2_top3", "top1_mean", "top1_worst", "mean_gap", "median_gap"]:
            values = [s[metric] for s in all_data["all_score_separations"] if s[metric] is not None]
            if values:
                print_statistics(f"  {metric}", values)

    print("\n" + "="*80)
    print("Analysis Complete")
    print("="*80)


if __name__ == "__main__":
    main()
