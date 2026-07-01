#!/usr/bin/env python3
"""
NYPC 2026 STEP 6A - Data-Driven Weight Sweep Runner
Weight 하나를 자동으로 변경하며 벤치마크를 반복 실행합니다.

원칙:
- One Change Only: 한 번에 하나의 Weight만 변경
- Evaluation Logic / Candidate Generator / 게임 로직 변경 X
- submission.py의 Weights.from_env()를 통해 환경변수 주입

사용 예:
  python scripts/weight_sweep_runner.py
"""

import os
import sys
import json
import subprocess
import time
from pathlib import Path
from datetime import datetime


########################################
# Experiment Configuration
########################################

# VERIFY_MODE: True면 가벼운 검증 (3 match × 3 values), False면 본격 Sweep
# STEP 6E: Adaptive Weight Sweep Framework
VERIFY_MODE = False
TOTAL_MATCHES = 100

# ===== Adaptive Experiment Configuration =====
# One Change Only + Early Stop Rule
ADAPTIVE_ENABLED = True           # Adaptive Experiment 활성화
INITIAL_MATCHES = 20              # 첫 판 수 (Adaptive 판단용)
GAP_THRESHOLD = 1.0               # TRAIN-MOVE Gap 변화 임계값 (이하이면 "거의 없음")
ADDITIONAL_MATCHES_STEP1 = 50     # Case 2: 추가 Match 수
ADDITIONAL_MATCHES_STEP2 = 100    # Case 3: 추가 Match 수
MAX_MATCHES = 200                 # 최대 Match 수
# ============================================

# Weight Sweep 대상 정의
WEIGHT_SWEEPS = [
    # ① w_train_n (우선순위 1)
    {
        "name": "w_train_n",
        "env_var": "W_TRAIN_N",
        "values": [50, 20, 5] if VERIFY_MODE else [50, 30, 20, 15, 10, 7, 5, 3, 1],
        "default": 50.0,
        "description": "TRAIN 행동 가중치"
    },
    # ② w_move_cost (우선순위 2)
    {
        "name": "w_move_cost",
        "env_var": "W_MOVE_COST",
        "values": [-4, -3, -2, -1],
        "default": -10.0,
        "description": "STEP 6D: Fine Sweep Around Threshold"
    },
    # ③ w_turns_to_enemy_hq (우선순위 3)
    {
        "name": "w_turns_to_enemy_hq",
        "env_var": "W_TURNS_TO_ENEMY_HQ",
        "values": [-1, -5, -10, -20, -50, -100],
        "default": -1.0,
        "description": "적 HQ 근접 가중치"
    }
]

# 어떤 Sweep을 실행할지 (순서대로)
# 0: w_train_n, 1: w_move_cost, 2: w_turns_to_enemy_hq
ACTIVE_SWEEP_INDICES = [1]

# 경기 설정
START_SEED = 1             # 시작 시드
MATCH_TIMEOUT = 300        # 개별 경기 타임아웃 (초)
PLAYER_LEFT = "python submission.py"
PLAYER_RIGHT = "python submission.py"

# 경로 설정
PROJECT_ROOT = Path(__file__).parent.parent
TESTING_TOOL = PROJECT_ROOT / "tools" / "testing-tool" / "testing-tool.py"
BUILD_SCRIPT = PROJECT_ROOT / "build.py"
SWEEP_BASE_DIR = PROJECT_ROOT / "logs" / "weight_sweep_step6e"
REPORT_DIR = PROJECT_ROOT / "logs" / "weight_sweep_step6e" / "report"
########################################


def setup_env(weight_sweep, value):
    """환경변수 설정 (submission.py의 Weights.from_env()가 읽음)"""
    env = os.environ.copy()
    env[weight_sweep["env_var"]] = str(value)
    return env


def parse_preliminary_metrics(log_files):
    """로그 파일들에서 Preliminary Metric 계산 (Adaptive 판단용)

    Returns:
        dict: {
            "move_pct": float,
            "wait_pct": float,
            "train_pct": float,
            "upgrade_pct": float,
            "avg_top1_score": float,
            "avg_top2_score": float,
            "avg_gap": float,
            "sample_count": int
        }
    """
    from collections import defaultdict
    import statistics

    if not log_files:
        return {
            "move_pct": 0.0, "wait_pct": 0.0, "train_pct": 0.0, "upgrade_pct": 0.0,
            "avg_top1_score": 0.0, "avg_top2_score": 0.0, "avg_gap": 0.0, "sample_count": 0
        }

    behavior_counts = defaultdict(int)
    top1_scores = []
    top2_scores = []
    gaps = []

    for log_path in log_files:
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # Debug 라인 파싱
            for line in lines:
                for side in ["LEFT", "RIGHT"]:
                    prefix = f"# Debug {side}:"
                    if line.startswith(prefix):
                        try:
                            import json
                            json_str = line[len(prefix):].strip()
                            obj = json.loads(json_str)

                            # Behavior Distribution (MOVE/TRAIN/UPGRADE/WAIT)
                            if "chosen_train" in obj:
                                train = obj.get("chosen_train", 0)
                                moves = obj.get("chosen_moves", 0)
                                upgrades = obj.get("chosen_upgrades", 0)
                                behavior_counts["train"] += train
                                behavior_counts["moves"] += moves
                                behavior_counts["upgrades"] += upgrades
                                if train == 0 and moves == 0 and upgrades == 0:
                                    behavior_counts["wait"] += 1

                            # Score Statistics
                            if "best_score" in obj:
                                top1_scores.append(obj["best_score"])
                            if "candidates" in obj:
                                candidates = obj["candidates"]
                                scores = sorted([c["score"] for c in candidates if c.get("affordable", False)], reverse=True)
                                if len(scores) >= 2:
                                    top2_scores.append(scores[1])
                                    gaps.append(scores[0] - scores[1])
                        except (json.JSONDecodeError, KeyError, ValueError):
                            continue
        except Exception:
            continue

    total_behavior = sum(behavior_counts.values()) or 1
    total = len(log_files)

    return {
        "move_pct": round(100.0 * behavior_counts["moves"] / total_behavior, 2),
        "wait_pct": round(100.0 * behavior_counts["wait"] / total_behavior, 2),
        "train_pct": round(100.0 * behavior_counts["train"] / total_behavior, 2),
        "upgrade_pct": round(100.0 * behavior_counts["upgrades"] / total_behavior, 2),
        "avg_top1_score": round(statistics.mean(top1_scores), 4) if top1_scores else 0.0,
        "avg_top2_score": round(statistics.mean(top2_scores), 4) if top2_scores else 0.0,
        "avg_gap": round(statistics.mean(gaps), 4) if gaps else 0.0,
        "sample_count": total
    }


def run_build():
    """build.py 실행 (submission.py 재생성)"""
    print(f"  [Build] {BUILD_SCRIPT.name} 실행 중...")
    result = subprocess.run(
        ["python", str(BUILD_SCRIPT)],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print(f"  [Build] 실패: {result.stderr}")
        return False
    print(f"  [Build] 성공")
    return True


def run_match(seed, log_path, env):
    """단일 경기 실행"""
    cmd = [
        "python",
        str(TESTING_TOOL),
        "--seed", str(seed),
        "--exec1", PLAYER_LEFT,
        "--exec2", PLAYER_RIGHT,
        "--log", str(log_path)
    ]
    try:
        result = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=MATCH_TIMEOUT,
            env=env
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        return False
    except Exception as e:
        print(f"  [Match {seed}] 오류: {e}")
        return False


def run_sweep_for_weight(weight_sweep):
    """하나의 Weight에 대해 Adaptive Sweep 실행"""
    name = weight_sweep["name"]
    env_var = weight_sweep["env_var"]
    values = weight_sweep["values"]
    default = weight_sweep["default"]

    print(f"\n{'='*70}")
    print(f"[Sweep] {name} ({weight_sweep['description']})")
    print(f"  Env Var: {env_var}")
    print(f"  Default: {default}")
    print(f"  Values: {values}")
    print(f"  Adaptive: {ADAPTIVE_ENABLED}, Initial: {INITIAL_MATCHES}, Max: {MAX_MATCHES}")
    print(f"{'='*70}")

    # Sweep 디렉토리 생성
    sweep_dir = SWEEP_BASE_DIR / name
    sweep_dir.mkdir(parents=True, exist_ok=True)

    # Build 1회 실행
    if not run_build():
        print(f"  [ERROR] Build 실패. Sweep 중단.")
        return {}

    results = {}

    for value in values:
        value_dir = sweep_dir / f"{name}_{value}"
        value_dir.mkdir(parents=True, exist_ok=True)

        # Adaptive 판단용: 이전 preliminary metric 저장
        prev_prelim_metric = None

        # 목표 Match 수 (Adaptive로 증가할 수 있음)
        target_matches = INITIAL_MATCHES if ADAPTIVE_ENABLED else TOTAL_MATCHES
        max_this_value = INITIAL_MATCHES if ADAPTIVE_ENABLED else TOTAL_MATCHES

        print(f"\n  --- {name} = {value} (초기 {INITIAL_MATCHES} match) ---")

        env = setup_env(weight_sweep, value)
        success_count = 0
        skip_count = 0
        fail_count = 0
        early_stopped = False
        adaptive_decisions = []

        start_time = time.time()

        for i in range(MAX_MATCHES):
            match_num = i + 1
            seed = START_SEED + i
            log_filename = f"match_{i:03d}.log"
            log_filepath = value_dir / log_filename

            # 기존 로그가 있으면 건너뛰기
            if log_filepath.exists():
                skip_count += 1
                success_count += 1
                # 기존 로그도 preliminary metric에 포함
                if match_num <= max_this_value:
                    pass
                if match_num >= target_matches:
                    break
                continue

            # 목표 Match 수에 도달했으면 종료
            if match_num > target_matches:
                break

            success = run_match(seed, log_filepath, env)
            if success:
                success_count += 1
                if (match_num % 10 == 0) or (match_num == INITIAL_MATCHES):
                    print(f"    [{match_num}/{target_matches}] OK", flush=True)
            else:
                fail_count += 1
                if (match_num % 10 == 0) or (match_num == INITIAL_MATCHES):
                    print(f"    [{match_num}/{target_matches}] FAIL", flush=True)

            # Adaptive 판단 (INITIAL_MATCHES 이후, Adaptive enabled일 때)
            if ADAPTIVE_ENABLED and match_num == INITIAL_MATCHES:
                # Preliminary metric 계산
                log_files = sorted(value_dir.glob("match_*.log"))[:INITIAL_MATCHES]
                prelim_metric = parse_preliminary_metrics(log_files)
                prev_prelim_metric = prelim_metric

                print(f"    [Adaptive Check] MOVE%={prelim_metric['move_pct']}%, "
                      f"WAIT%={prelim_metric['wait_pct']}%, "
                      f"avg_gap={prelim_metric['avg_gap']}")

                # Case 1: Early Stop 판단
                # MOVE%=0% AND WAIT%>=97% AND TRAIN-MOVE Gap 변화 거의 없음
                if (prelim_metric['move_pct'] == 0.0 and
                    prelim_metric['wait_pct'] >= 97.0):
                    print(f"    [EARLY STOP] Case 1: MOVE%=0%, WAIT%>=97%")
                    early_stopped = True
                    adaptive_decisions.append({
                        "at_match": INITIAL_MATCHES,
                        "case": "Case1_EarlyStop",
                        "move_pct": prelim_metric['move_pct'],
                        "wait_pct": prelim_metric['wait_pct']
                    })
                    break

                # Case 2: 추가 50 Match (MOVE% 증가)
                elif prelim_metric['move_pct'] > 0.0:
                    target_matches = INITIAL_MATCHES + ADDITIONAL_MATCHES_STEP1
                    print(f"    [CONTINUE] Case 2: MOVE%={prelim_metric['move_pct']}% > 0, "
                          f"추가 {ADDITIONAL_MATCHES_STEP1} match (total: {target_matches})")
                    adaptive_decisions.append({
                        "at_match": INITIAL_MATCHES,
                        "case": "Case2_Continue50",
                        "move_pct": prelim_metric['move_pct'],
                        "wait_pct": prelim_metric['wait_pct']
                    })

            elif ADAPTIVE_ENABLED and match_num > INITIAL_MATCHES and prev_prelim_metric:
                # 추가 Match 수행 후再次 판단 (50 match 후)
                # 이 때 Preliminary metric을 다시 계산
                pass  # Case 3은 50 match 후 다시 판단

        # 50 match 후再次 판단 (Case 3)
        if ADAPTIVE_ENABLED and not early_stopped and success_count >= INITIAL_MATCHES + ADDITIONAL_MATCHES_STEP1:
            log_files = sorted(value_dir.glob("match_*.log"))[:INITIAL_MATCHES + ADDITIONAL_MATCHES_STEP1]
            prelim_metric = parse_preliminary_metrics(log_files)

            # Case 3: MOVE% 계속 증가 → 추가 100 Match
            if prelim_metric['move_pct'] > prev_prelim_metric['move_pct']:
                target_matches = INITIAL_MATCHES + ADDITIONAL_MATCHES_STEP1 + ADDITIONAL_MATCHES_STEP2
                print(f"    [CONTINUE] Case 3: MOVE% 증가 ({prev_prelim_metric['move_pct']}% -> {prelim_metric['move_pct']}%), "
                      f"추가 {ADDITIONAL_MATCHES_STEP2} match (total: {target_matches})")
                adaptive_decisions.append({
                    "at_match": INITIAL_MATCHES + ADDITIONAL_MATCHES_STEP1,
                    "case": "Case3_Continue100",
                    "move_pct": prelim_metric['move_pct'],
                    "prev_move_pct": prev_prelim_metric['move_pct']
                })

                # 추가 Match 수행
                for i in range(INITIAL_MATCHES + ADDITIONAL_MATCHES_STEP1, target_matches):
                    match_num = i + 1
                    seed = START_SEED + i
                    log_filename = f"match_{i:03d}.log"
                    log_filepath = value_dir / log_filename

                    if log_filepath.exists():
                        continue

                    success = run_match(seed, log_filepath, env)
                    if success:
                        success_count += 1
                        if match_num % 10 == 0:
                            print(f"    [{match_num}/{target_matches}] OK", flush=True)
                    else:
                        fail_count += 1

        elapsed = time.time() - start_time
        final_matches = success_count - skip_count

        results[str(value)] = {
            "weight_value": value,
            "env_var": env_var,
            "total_matches_requested": TOTAL_MATCHES,
            "actual_matches": final_matches,
            "success": success_count,
            "skipped": skip_count,
            "failed": fail_count,
            "elapsed_sec": round(elapsed, 2),
            "early_stopped": early_stopped,
            "adaptive_decisions": adaptive_decisions,
            "log_dir": str(value_dir)
        }

        print(f"  --- 결과: 성공={success_count}, 건너뜀={skip_count}, 실패={fail_count}, "
              f"실제 match={final_matches}, 소요={elapsed:.1f}초 ---")
        if early_stopped:
            print(f"  [EARLY STOP] {INITIAL_MATCHES} match에서 조기 종료")
        elif adaptive_decisions:
            print(f"  [ADAPTIVE] 결정: {[d['case'] for d in adaptive_decisions]}")

    # Sweep 요약 저장
    summary_path = sweep_dir / "sweep_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump({
            "weight_name": name,
            "env_var": env_var,
            "default": default,
            "description": weight_sweep["description"],
            "values": values,
            "results": results,
            "timestamp": datetime.now().isoformat()
        }, f, indent=2, ensure_ascii=False)

    print(f"\n[Sweep] {name} 요약 저장: {summary_path}")
    return results


def main():
    print("="*70)
    print("NYPC 2026 STEP 6E - Adaptive Weight Sweep Framework")
    print("="*70)
    print(f"Project Root: {PROJECT_ROOT}")
    print(f"Sweep Base Dir: {SWEEP_BASE_DIR}")
    print(f"Active Sweep Indices: {ACTIVE_SWEEP_INDICES}")
    print(f"Adaptive Enabled: {ADAPTIVE_ENABLED}")
    print(f"Initial Matches: {INITIAL_MATCHES}, Max: {MAX_MATCHES}")

    SWEEP_BASE_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    all_results = {}
    for idx in ACTIVE_SWEEP_INDICES:
        if idx >= len(WEIGHT_SWEEPS):
            print(f"  [WARN] 잘못된 Sweep 인덱스: {idx}")
            continue
        weight_sweep = WEIGHT_SWEEPS[idx]
        all_results[weight_sweep["name"]] = run_sweep_for_weight(weight_sweep)

    # 전체 Sweep 요약 저장
    master_summary_path = SWEEP_BASE_DIR / "master_summary.json"
    with open(master_summary_path, "w", encoding="utf-8") as f:
        json.dump({
            "active_sweeps": [WEIGHT_SWEEPS[i]["name"] for i in ACTIVE_SWEEP_INDICES],
            "total_matches_per_value": TOTAL_MATCHES,
            "results": all_results,
            "timestamp": datetime.now().isoformat()
        }, f, indent=2, ensure_ascii=False)

    print("\n" + "="*70)
    print(f"전체 Sweep 완료. Master Summary: {master_summary_path}")
    print("="*70)
    print("\n다음 단계:")
    print(f"  1. python scripts/behavior_benchmark.py    # Behavior 메트릭 추출")
    print(f"  2. python scripts/weight_sweep_report.py    # 최종 Report + Ranking")


if __name__ == "__main__":
    main()
