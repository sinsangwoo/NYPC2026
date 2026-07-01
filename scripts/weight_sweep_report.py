#!/usr/bin/env python3
"""
NYPC 2026 STEP 6A - Weight Sweep Report
behavior_benchmark 결과를 받아 다음을 수행:
  - 8개 자동 분석 (MOVE/Stronghold/Upgrade/HQ/Dominance/Distribution)
  - Weight Sweep Report (각 Weight별 핵심 지표)
  - 최종 Ranking (추천/보류/폐기)

사용 예:
  python scripts/weight_sweep_report.py
"""

import os
import sys
import json
import statistics
from pathlib import Path
from collections import defaultdict
from datetime import datetime


########################################
# Experiment Configuration
########################################
PROJECT_ROOT = Path(__file__).parent.parent
REPORT_DIR = PROJECT_ROOT / "logs" / "weight_sweep_step6e" / "report"

# 입력 파일
BEHAVIOR_SUMMARY_JSON = REPORT_DIR / "behavior_summary.json"
BEHAVIOR_SUMMARY_CSV = REPORT_DIR / "behavior_summary.csv"

# 출력 파일
WEIGHT_REPORT_TXT = REPORT_DIR / "weight_sweep_report.txt"
WEIGHT_RANKING_CSV = REPORT_DIR / "weight_ranking.csv"
WEIGHT_AUTO_ANALYSIS = REPORT_DIR / "auto_analysis.json"

# 평가 기준 (튜닝 가능)
# 추천/보류/폐기 기준:
# - 추천: Win rate > 5% (Baseline 0% 대비) AND Dominance < 50% AND MOVE > 0
# - 보류: 어느 한 조건만 만족
# - 폐기: 모두 미달
CRITERIA = {
    "min_win_rate_pct": 5.0,         # Baseline 대비 최소 승률
    "max_top_dominance_pct": 50.0,   # Dominance 상한
    "min_move_select_rate": 0.01,    # 최소 MOVE 발생율
    "min_upgrade_select_count": 0    # 최소 UPGRADE 1개 이상 (선택됨)
}
########################################


def load_summary():
    """behavior_benchmark의 JSON 요약 로드"""
    if not BEHAVIOR_SUMMARY_JSON.exists():
        print(f"[ERROR] {BEHAVIOR_SUMMARY_JSON} 없음")
        print("먼저 python scripts/behavior_benchmark.py 실행")
        return None

    with open(BEHAVIOR_SUMMARY_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def auto_analyze_value(base_value_data, value_data, weight_name, value):
    """8개 자동 분석 질문에 답"""
    if base_value_data is None:
        return {
            "q1_move_increased": "N/A (no baseline)",
            "q2_stronghold_increased": "N/A",
            "q3_upgrade_candidate_generated": "N/A",
            "q4_upgrade_selected": "N/A",
            "q5_hq_approach_increased": "N/A",
            "q6_win_rate_increased": "N/A",
            "q7_dominance_improved": "N/A",
            "q8_final_score_normal": "N/A"
        }

    base_bm = base_value_data["behavior_metrics"]
    cur_bm = value_data["behavior_metrics"]

    def safe_float(v, default=0.0):
        if v == "N/A" or v is None:
            return default
        return float(v)

    def safe_int(v, default=0):
        if v == "N/A" or v is None:
            return default
        return int(v)

    # ① MOVE 증가 여부
    base_move = safe_float(base_bm.get("move_select_rate"))
    cur_move = safe_float(cur_bm.get("move_select_rate"))
    q1 = "Yes" if cur_move > base_move + 0.001 else "No"
    q1_delta = round(cur_move - base_move, 4)

    # ② Stronghold 방문 증가
    base_sh = safe_int(base_bm.get("strongholds_visit_count"))
    cur_sh = safe_int(cur_bm.get("strongholds_visit_count"))
    q2 = "Yes" if cur_sh > base_sh else "No"
    q2_delta = cur_sh - base_sh

    # ③ UPGRADE 후보 생성
    cur_upg_cand = safe_int(cur_bm.get("upgrade_candidate_count"))
    q3 = "Yes" if cur_upg_cand > 0 else "No"
    q3_count = cur_upg_cand

    # ④ UPGRADE 실제 선택
    cur_upg_sel = safe_int(cur_bm.get("upgrade_select_count"))
    q4 = "Yes" if cur_upg_sel > 0 else "No"
    q4_count = cur_upg_sel

    # ⑤ HQ 접근 증가
    base_hq = safe_float(base_bm.get("avg_hq_approach"))
    cur_hq = safe_float(cur_bm.get("avg_hq_approach"))
    q5 = "Yes" if cur_hq > base_hq + 0.001 else "No"
    q5_delta = round(cur_hq - base_hq, 4)

    # ⑥ 승률 증가
    base_wr = base_value_data["win_rate_pct"]
    cur_wr = value_data["win_rate_pct"]
    q6 = "Yes" if cur_wr > base_wr else "No"
    q6_delta = round(cur_wr - base_wr, 2)

    # ⑦ Dominance 개선
    base_dom = base_value_data["top_dominance"]["pct"]
    cur_dom = value_data["top_dominance"]["pct"]
    q7 = "Yes" if cur_dom < base_dom else "No"
    q7_delta = round(cur_dom - base_dom, 2)

    # ⑧ Final Score Distribution 정상
    cur_fsd = value_data["final_score_distribution"]
    cur_std = cur_fsd["std"]
    # std > 0 (값들이 분포되어 있음) AND max != min (구분됨)
    q8 = "Yes" if cur_std > 0.01 and cur_fsd["max"] != cur_fsd["min"] else "No"

    return {
        "weight_name": weight_name,
        "weight_value": value,
        "q1_move_increased": q1, "q1_delta": q1_delta,
        "q2_stronghold_increased": q2, "q2_delta": q2_delta,
        "q3_upgrade_candidate_generated": q3, "q3_count": q3_count,
        "q4_upgrade_selected": q4, "q4_count": q4_count,
        "q5_hq_approach_increased": q5, "q5_delta": q5_delta,
        "q6_win_rate_increased": q6, "q6_delta": q6_delta,
        "q7_dominance_improved": q7, "q7_delta": q7_delta,
        "q8_final_score_normal": q8,
        "current_win_rate_pct": cur_wr,
        "current_dominance_pct": cur_dom,
        "current_top_dominance_feature": value_data["top_dominance"]["feature"]
    }


def evaluate_value(analysis, value_data):
    """추천/보류/폐기 평가"""
    wr = analysis["current_win_rate_pct"]
    dom = analysis["current_dominance_pct"]
    move_pct = value_data["behavior_distribution"]["MOVE"]
    upg_sel = analysis["q4_count"]

    # 추천 조건
    cond_win = wr >= CRITERIA["min_win_rate_pct"]
    cond_dom = dom < CRITERIA["max_top_dominance_pct"]
    cond_move = move_pct >= 0.5  # Behavior 분포의 0.5% 이상
    cond_upg = upg_sel > 0

    passed = sum([cond_win, cond_dom, cond_move, cond_upg])

    if passed >= 3:
        return "추천"
    elif passed >= 1:
        return "보류"
    else:
        return "폐기"


def generate_report(summary):
    """Weight Sweep Report 텍스트 생성"""
    lines = []
    lines.append("="*80)
    lines.append("NYPC 2026 STEP 6A - Weight Sweep Report")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("="*80)

    auto_analyses = {}

    for weight_name, sweep_data in summary["sweeps"].items():
        if not sweep_data:
            continue

        # baseline (default value, typically first)
        values_sorted = sorted(sweep_data.keys(), key=lambda x: float(x) if isinstance(x, (int, float)) else 0)
        baseline_value = values_sorted[-1]  # 최대값을 baseline으로 (TRAIN의 경우 50이 default)
        baseline_data = sweep_data[baseline_value]

        lines.append(f"\n## Weight: {weight_name}")
        lines.append(f"   Baseline (default) = {baseline_value}")
        lines.append(f"   Baseline WinRate: {baseline_data['win_rate_pct']}%, "
                     f"Top Dominance: {baseline_data['top_dominance']['feature']}({baseline_data['top_dominance']['pct']}%)")

        lines.append("")
        lines.append("="*120)
        lines.append(f"{'Value':<8} {'Win':<5} {'Lose':<5} {'Draw':<5} {'MOVE%':<7} {'TRAIN%':<8} {'UPG%':<7} "
                     f"{'ShVisit':<8} {'HQ Dist':<8} {'First MOVE':<10} {'First UPG':<10} "
                     f"{'AvgScore':<10} {'T1-T2':<8} {'Dom':<8} {'ScoreStd':<10} {'Eval':<6}")
        lines.append("="*120)

        auto_analyses[weight_name] = {}

        for value in values_sorted:
            data = sweep_data[value]
            bm = data["behavior_metrics"]
            analysis = auto_analyze_value(baseline_data, data, weight_name, value)
            evaluation = evaluate_value(analysis, data)
            auto_analyses[weight_name][str(value)] = analysis

            top1_top2_gap = bm.get("avg_top1_top2_gap", "N/A")
            fsd = data["final_score_distribution"]
            avg_score = fsd["mean"]
            score_std = fsd["std"]

            row = (
                f"{value:<8} "
                f"{data['win']:<5} "
                f"{data['lose']:<5} "
                f"{data['draw']:<5} "
                f"{data['behavior_distribution']['MOVE']:<7} "
                f"{data['behavior_distribution']['TRAIN']:<8} "
                f"{data['behavior_distribution']['UPGRADE']:<7} "
                f"{bm.get('strongholds_visit_count', 'N/A'):<8} "
                f"{bm.get('avg_hq_distance', 'N/A'):<8} "
                f"{str(bm.get('first_move_turn', 'N/A')):<10} "
                f"{str(bm.get('first_upgrade_turn', 'N/A')):<10} "
                f"{avg_score:<10} "
                f"{top1_top2_gap:<8} "
                f"{data['top_dominance']['pct']:<8} "
                f"{score_std:<10} "
                f"{evaluation:<6}"
            )
            lines.append(row)

        lines.append("="*120)

        # 8개 자동 분석 요약
        lines.append(f"\n### 8개 자동 분석 ({weight_name})")
        lines.append(f"{'Value':<8} {'Q1(MOVE↑)':<11} {'Q2(SH↑)':<10} {'Q3(UPG cand)':<13} {'Q4(UPG sel)':<12} "
                     f"{'Q5(HQ↑)':<10} {'Q6(WR↑)':<10} {'Q7(Dom↑)':<10} {'Q8(Score)':<10} {'Eval':<6}")
        lines.append("-"*120)
        for value in values_sorted:
            analysis = auto_analyses[weight_name][str(value)]
            row = (
                f"{value:<8} "
                f"{analysis['q1_move_increased']+'('+str(analysis['q1_delta'])+')':<11} "
                f"{analysis['q2_stronghold_increased']+'('+str(analysis['q2_delta'])+')':<10} "
                f"{analysis['q3_upgrade_candidate_generated']+'('+str(analysis['q3_count'])+')':<13} "
                f"{analysis['q4_upgrade_selected']+'('+str(analysis['q4_count'])+')':<12} "
                f"{analysis['q5_hq_approach_increased']+'('+str(analysis['q5_delta'])+')':<10} "
                f"{analysis['q6_win_rate_increased']+'('+str(analysis['q6_delta'])+')':<10} "
                f"{analysis['q7_dominance_improved']+'('+str(analysis['q7_delta'])+')':<10} "
                f"{analysis['q8_final_score_normal']:<10} "
                f"{evaluate_value(analysis, sweep_data[value]):<6}"
            )
            lines.append(row)
        lines.append("-"*120)

    # 통합 요약 테이블 (모든 weight side-by-side)
    lines.append("\n" + "="*80)
    lines.append("통합 Behavior 요약 테이블 (모든 Weight 비교)")
    lines.append("="*80)
    lines.append(
        f"{'Weight':<18} {'Value':<8} {'Win/D/L':<10} "
        f"{'MOVE%':<7} {'TRAIN%':<8} {'UPG%':<7} {'WAIT%':<7} "
        f"{'ShVisit':<8} {'ShCap':<6} {'Base':<6} "
        f"{'UniqueReg':<10} {'HQ Dist':<9} "
        f"{'Top1':<8} {'T1-T2':<8} {'Dom%':<7} {'Std':<7}"
    )
    lines.append("-"*180)

    integrated_rows = []
    for weight_name, sweep_data in summary["sweeps"].items():
        for value, data in sweep_data.items():
            bm = data["behavior_metrics"]
            row_str = (
                f"{weight_name:<18} {str(value):<8} "
                f"{data['win']}/{data['draw']}/{data['lose']:<8} "
                f"{data['behavior_distribution']['MOVE']:<7} "
                f"{data['behavior_distribution']['TRAIN']:<8} "
                f"{data['behavior_distribution']['UPGRADE']:<7} "
                f"{data['behavior_distribution']['WAIT']:<7} "
                f"{bm.get('strongholds_visit_count', 0):<8} "
                f"{bm.get('stronghold_capture_count', 0):<6} "
                f"{bm.get('base_construction_count', 0):<6} "
                f"{bm.get('unique_regions_visited', 0):<10} "
                f"{bm.get('avg_hq_distance', 999):<9} "
                f"{bm.get('avg_top1_score', 0):<8} "
                f"{bm.get('avg_top1_top2_gap', 0):<8} "
                f"{data['top_dominance']['pct']:<7} "
                f"{data['final_score_distribution']['std']:<7}"
            )
            lines.append(row_str)
            integrated_rows.append({
                "weight_name": weight_name,
                "value": value,
                "data": data,
                "bm": bm
            })
    lines.append("="*180)

    # 추천 (상위 2-3개) - 행동 기반 점수
    # 점수 = (MOVE% * 5) + (UPG 선택 * 30) + (Stronghold Capture * 50) + ((100-Dominance) * 0.5) + (WinRate * 0.3)
    lines.append("\n" + "="*80)
    lines.append("상위 추천 Weight (행동 우선, 승률 보조)")
    lines.append("="*80)
    lines.append("점수 = MOVE%×5 + UPG선택×30 + ShCap×50 + (100-Dom%)×0.5 + WinRate%×0.3")
    lines.append("-"*120)

    for r in integrated_rows:
        d = r["data"]
        bm = r["bm"]
        move_pct = d["behavior_distribution"]["MOVE"]
        upg_sel = bm.get("upgrade_select_count", 0)
        sh_cap = bm.get("stronghold_capture_count", 0)
        dom = d["top_dominance"]["pct"]
        wr = d["win_rate_pct"]
        score = (move_pct * 5) + (upg_sel * 30) + (sh_cap * 50) + ((100 - dom) * 0.5) + (wr * 0.3)
        r["recommend_score"] = round(score, 2)

    integrated_rows.sort(key=lambda x: -x["recommend_score"])

    lines.append(f"{'Rank':<5} {'Weight':<18} {'Value':<8} {'RecScore':<10} {'MOVE%':<7} {'UPG':<5} {'ShCap':<6} {'Dom%':<6} {'Win%':<6} {'Verdict':<8}")
    lines.append("-"*120)
    for rank, r in enumerate(integrated_rows[:5], 1):  # 상위 5개 표시
        d = r["data"]
        bm = r["bm"]
        verdict = "강력 추천" if rank <= 2 else ("추천" if rank <= 3 else "보류")
        lines.append(
            f"{rank:<5} {r['weight_name']:<18} {str(r['value']):<8} "
            f"{r['recommend_score']:<10} "
            f"{d['behavior_distribution']['MOVE']:<7} "
            f"{bm.get('upgrade_select_count', 0):<5} "
            f"{bm.get('stronghold_capture_count', 0):<6} "
            f"{d['top_dominance']['pct']:<6} "
            f"{d['win_rate_pct']:<6} {verdict:<8}"
        )
    lines.append("="*120)

    # 최종 Ranking (기존 - 모든 Weight)
    lines.append("\n" + "="*80)
    lines.append("최종 Ranking (전체 Weight)")
    lines.append("="*80)
    lines.append(f"{'Weight':<20} {'Value':<10} {'WinRate%':<10} {'DrawRate%':<12} {'LoseRate%':<11} "
                 f"{'MOVE%':<8} {'SH':<5} {'UPG':<5} {'HQ Dist':<10} {'Dom%':<8} {'평가':<8}")
    lines.append("-"*120)

    ranking_rows = []
    for weight_name, sweep_data in summary["sweeps"].items():
        for value, data in sweep_data.items():
            analysis = auto_analyses[weight_name].get(str(value), {})
            evaluation = evaluate_value(analysis, data) if analysis else "N/A"
            bm = data["behavior_metrics"]
            row = {
                "weight_name": weight_name,
                "value": value,
                "win_rate_pct": data["win_rate_pct"],
                "draw_rate_pct": data["draw_rate_pct"],
                "lose_rate_pct": data["lose_rate_pct"],
                "move_pct": data["behavior_distribution"]["MOVE"],
                "stronghold": bm.get("strongholds_visit_count", "N/A"),
                "upgrade_select": bm.get("upgrade_select_count", "N/A"),
                "hq_distance": bm.get("avg_hq_distance", "N/A"),
                "dominance_pct": data["top_dominance"]["pct"],
                "evaluation": evaluation
            }
            ranking_rows.append(row)

    # 점수 = (WinRate * 0.5) + (100 - Dominance) * 0.3 + (MOVE% * 0.2)
    for r in ranking_rows:
        score = (r["win_rate_pct"] * 0.5) + ((100 - r["dominance_pct"]) * 0.3) + (r["move_pct"] * 0.2)
        r["score"] = round(score, 2)

    ranking_rows.sort(key=lambda x: -x["score"])

    for r in ranking_rows:
        lines.append(
            f"{r['weight_name']:<20} {str(r['value']):<10} "
            f"{r['win_rate_pct']:<10} {r['draw_rate_pct']:<12} {r['lose_rate_pct']:<11} "
            f"{r['move_pct']:<8} {str(r['stronghold']):<5} {str(r['upgrade_select']):<5} "
            f"{str(r['hq_distance']):<10} {r['dominance_pct']:<8} {r['evaluation']:<8}"
        )
    lines.append("="*120)

    return "\n".join(lines), ranking_rows, auto_analyses, integrated_rows


def main():
    print("="*70)
    print("NYPC 2026 STEP 6A - Weight Sweep Report")
    print("="*70)

    summary = load_summary()
    if summary is None:
        return

    # Report 생성
    report_txt, ranking_rows, auto_analyses, integrated_rows = generate_report(summary)

    # 파일 저장
    with open(WEIGHT_REPORT_TXT, "w", encoding="utf-8") as f:
        f.write(report_txt)
    print(f"[OK] Report 저장: {WEIGHT_REPORT_TXT}")

    # CSV 저장 (추천 Ranking)
    with open(WEIGHT_RANKING_CSV, "w", encoding="utf-8") as f:
        headers = [
            "rank", "weight_name", "value", "score",
            "win_rate_pct", "draw_rate_pct", "lose_rate_pct",
            "move_pct", "stronghold", "upgrade_select", "hq_distance",
            "dominance_pct", "evaluation"
        ]
        f.write(",".join(headers) + "\n")
        for rank, r in enumerate(ranking_rows, 1):
            row = [rank, r["weight_name"], r["value"], r["score"],
                   r["win_rate_pct"], r["draw_rate_pct"], r["lose_rate_pct"],
                   r["move_pct"], r["stronghold"], r["upgrade_select"], r["hq_distance"],
                   r["dominance_pct"], r["evaluation"]]
            f.write(",".join(str(x) for x in row) + "\n")
    print(f"[OK] Ranking CSV 저장: {WEIGHT_RANKING_CSV}")

    # 추천 Ranking CSV (행동 기반)
    RECOMMEND_CSV = REPORT_DIR / "recommend_ranking.csv"
    with open(RECOMMEND_CSV, "w", encoding="utf-8") as f:
        headers = [
            "rank", "weight_name", "value", "recommend_score",
            "move_pct", "train_pct", "upgrade_pct", "wait_pct",
            "win_rate_pct", "draw_rate_pct", "lose_rate_pct",
            "stronghold_visit", "stronghold_capture", "base_construction",
            "unique_regions_visited", "avg_hq_distance",
            "avg_top1_score", "avg_top1_top2_gap",
            "dominance_pct", "verdict"
        ]
        f.write(",".join(headers) + "\n")
        for rank, r in enumerate(integrated_rows, 1):
            d = r["data"]
            bm = r["bm"]
            verdict = "강력 추천" if rank <= 2 else ("추천" if rank <= 3 else "보류")
            row = [
                rank, r["weight_name"], r["value"], r["recommend_score"],
                d["behavior_distribution"]["MOVE"], d["behavior_distribution"]["TRAIN"],
                d["behavior_distribution"]["UPGRADE"], d["behavior_distribution"]["WAIT"],
                d["win_rate_pct"], d["draw_rate_pct"], d["lose_rate_pct"],
                bm.get("strongholds_visit_count", 0),
                bm.get("stronghold_capture_count", 0),
                bm.get("base_construction_count", 0),
                bm.get("unique_regions_visited", 0),
                bm.get("avg_hq_distance", 999),
                bm.get("avg_top1_score", 0),
                bm.get("avg_top1_top2_gap", 0),
                d["top_dominance"]["pct"],
                verdict
            ]
            f.write(",".join(str(x) for x in row) + "\n")
    print(f"[OK] Recommend Ranking CSV 저장: {RECOMMEND_CSV}")

    # 자동 분석 JSON
    with open(WEIGHT_AUTO_ANALYSIS, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "criteria": CRITERIA,
            "analyses": auto_analyses,
            "ranking": ranking_rows
        }, f, indent=2, ensure_ascii=False)
    print(f"[OK] Auto Analysis JSON 저장: {WEIGHT_AUTO_ANALYSIS}")

    # 화면 출력
    print("\n" + report_txt)

    print("\n" + "="*70)
    print("STEP 6A 완료")
    print("="*70)


if __name__ == "__main__":
    main()
