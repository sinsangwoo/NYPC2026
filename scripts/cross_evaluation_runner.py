#!/usr/bin/env python3
"""
NYPC 2026 - Cross Evaluation Framework
서로 다른 AI Profile끼리对战하여 승률을 측정합니다.

사용법:
  python scripts/cross_evaluation_runner.py              # 전체 Cross Evaluation 실행
  python scripts/cross_evaluation_runner.py --list       # AI Profile 목록 표시
  python scripts/cross_evaluation_runner.py --verify     # Lightweight 검증
"""

import os
import sys
import json
import time
import argparse
import subprocess
from pathlib import Path
from itertools import combinations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent
TESTING_TOOL = PROJECT_ROOT / "tools" / "testing-tool" / "testing-tool.py"
BUILD_SCRIPT = PROJECT_ROOT / "build.py"

########################################
# AI Profile 정의
# 새로운 AI를 추가하려면 이 사전에 Profile만 추가하면 됩니다.
########################################
AI_PROFILES = {
    # Baseline: 기본 Weight (w_move_cost=-10, w_train_n=50)
    "baseline": {
        "name": "Baseline",
        "description": "기본 AI (w_move_cost=-10, w_train_n=50)",
        "exec_left": "python submission.py",
        "exec_right": "python submission.py",
        "env": {}  # 환경변수 없음 = 기본 Weight 사용
    },
    # Move(-1): w_move_cost=-1 (MOVE% ≈ 16%)
    "move_minus_1": {
        "name": "Move(-1)",
        "description": "w_move_cost=-1 (MOVE 활성화)",
        "exec_left": "python submission.py",
        "exec_right": "python submission.py",
        "env": {"W_MOVE_COST": "-1"}
    },
    # Move(-2): w_move_cost=-2 (MOVE% ≈ 7%)
    "move_minus_2": {
        "name": "Move(-2)",
        "description": "w_move_cost=-2 (MOVE 부분 활성화)",
        "exec_left": "python submission.py",
        "exec_right": "python submission.py",
        "env": {"W_MOVE_COST": "-2"}
    },
    # Move(0): w_move_cost=0 (MOVE% ≈ 21%)
    "move_zero": {
        "name": "Move(0)",
        "description": "w_move_cost=0 (MOVE 역치 초과)",
        "exec_left": "python submission.py",
        "exec_right": "python submission.py",
        "env": {"W_MOVE_COST": "0"}
    },
}

# Cross Evaluation 설정
TOTAL_MATCHES = 20          # 각对战당 경기 수
START_SEED = 1             # 시작 시드
MATCH_TIMEOUT = 300        # 개별 경기 타임아웃 (초)
CROSS_EVAL_DIR = PROJECT_ROOT / "logs" / "cross_evaluation"

########################################
# Match Result Dataclass
########################################
@dataclass
class MatchResult:
    """각 경기의 결과"""
    match_id: int
    seed: int
    left_profile: str
    right_profile: str
    winner: str  # "LEFT", "RIGHT", "DRAW"
    left_score: int
    right_score: int
    total_turns: int
    execution_time_sec: float
    log_path: str


@dataclass
class PairwiseResult:
    """한 쌍의 Profile对战 결과"""
    left_profile: str
    right_profile: str
    total_matches: int
    left_wins: int
    right_wins: int
    draws: int
    left_win_rate: float
    right_win_rate: float
    draw_rate: float
    avg_turns: float
    matches: List[MatchResult] = field(default_factory=list)


########################################
# 유틸리티 함수
########################################
def run_build():
    """Build 실행"""
    try:
        result = subprocess.run(
            ["python", str(BUILD_SCRIPT)],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=60
        )
        return result.returncode == 0
    except Exception:
        return False


def parse_match_result(log_path: Path) -> Tuple[str, int, int, int]:
    """로그 파일에서 결과를 파싱

    Returns:
        (winner, left_score, right_score, total_turns)
    """
    winner = "DRAW"
    left_score = 0
    right_score = 0
    total_turns = 0

    try:
        with open(log_path, "r", encoding="utf-8") as f:
            content = f.read()

        # 총 턴 수 파싱
        if "total_turns" in content.lower() or "turn" in content.lower():
            for line in content.split("\n"):
                if "FINISH" in line:
                    # 예: "FINISH LEFT WIN" 또는 "FINISH DRAW"
                    parts = line.split()
                    if len(parts) >= 3:
                        if parts[1] == "LEFT":
                            winner = "LEFT"
                        elif parts[1] == "RIGHT":
                            winner = "RIGHT"
                        else:
                            winner = "DRAW"

        # Turn 수 파싱
        for line in content.split("\n"):
            if line.startswith("TURN "):
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        turn_num = int(parts[1])
                        total_turns = max(total_turns, turn_num)
                    except ValueError:
                        pass

        # HQ Health 기반 점수 파싱
        for line in content.split("\n"):
            if "LEFT HQ Health:" in line or "LEFT HQ:" in line:
                try:
                    health = int(line.split()[-1])
                    left_score = health
                except:
                    pass
            if "RIGHT HQ Health:" in line or "RIGHT HQ:" in line:
                try:
                    health = int(line.split()[-1])
                    right_score = health
                except:
                    pass

    except Exception:
        pass

    return winner, left_score, right_score, total_turns


def run_single_match(
    seed: int,
    left_profile: Dict,
    right_profile: Dict,
    log_path: Path,
    env_override: Optional[Dict] = None
) -> MatchResult:
    """단일 경기 실행"""
    # 환경변수 설정
    env = os.environ.copy()
    if env_override:
        env.update(env_override)

    # Profile별 환경변수 적용
    if left_profile.get("env"):
        env.update(left_profile["env"])
    if right_profile.get("env"):
        for k, v in right_profile["env"].items():
            env[f"RIGHT_{k}"] = v  # RIGHT側는 접두사 추가

    start_time = time.time()

    try:
        cmd = [
            "python",
            str(TESTING_TOOL),
            "--seed", str(seed),
            "--exec1", left_profile["exec_left"],
            "--exec2", right_profile["exec_right"],
            "--log", str(log_path)
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=MATCH_TIMEOUT,
            cwd=str(PROJECT_ROOT),
            env=env
        )

        execution_time = time.time() - start_time

        # 로그 파싱
        winner, left_score, right_score, total_turns = parse_match_result(log_path)

    except subprocess.TimeoutExpired:
        execution_time = time.time() - start_time
        winner = "DRAW"
        left_score = 0
        right_score = 0
        total_turns = 200
    except Exception as e:
        execution_time = time.time() - start_time
        winner = "DRAW"
        left_score = 0
        right_score = 0
        total_turns = 0

    return MatchResult(
        match_id=0,
        seed=seed,
        left_profile=left_profile["name"],
        right_profile=right_profile["name"],
        winner=winner,
        left_score=left_score,
        right_score=right_score,
        total_turns=total_turns,
        execution_time_sec=execution_time,
        log_path=str(log_path)
    )


def run_pairwise_evaluation(
    left_profile_id: str,
    right_profile_id: str,
    profile_map: Dict[str, Dict],
    output_dir: Path,
    total_matches: int = TOTAL_MATCHES
) -> PairwiseResult:
    """두 Profile간의对战 실행"""
    left_profile = profile_map[left_profile_id]
    right_profile = profile_map[right_profile_id]

    pair_dir = output_dir / f"{left_profile_id}_vs_{right_profile_id}"
    pair_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n  [{left_profile['name']}] vs [{right_profile['name']}]")

    matches = []
    left_wins = 0
    right_wins = 0
    draws = 0
    total_turns_sum = 0

    # Build 1회 실행
    if not run_build():
        print(f"    [ERROR] Build failed")
        return PairwiseResult(
            left_profile=left_profile_id,
            right_profile=right_profile_id,
            total_matches=0,
            left_wins=0,
            right_wins=0,
            draws=0,
            left_win_rate=0.0,
            right_win_rate=0.0,
            draw_rate=0.0,
            avg_turns=0.0
        )

    start_time = time.time()

    for i in range(total_matches):
        seed = START_SEED + i
        log_filename = f"match_{i:04d}.log"
        log_path = pair_dir / log_filename

        # 기존 로그 있으면 로드
        if log_path.exists():
            winner, ls, rs, tt = parse_match_result(log_path)
        else:
            result = run_single_match(seed, left_profile, right_profile, log_path)
            winner = result.winner
            ls = result.left_score
            rs = result.right_score
            tt = result.total_turns

        if winner == "LEFT":
            left_wins += 1
        elif winner == "RIGHT":
            right_wins += 1
        else:
            draws += 1

        total_turns_sum += tt

        if (i + 1) % 10 == 0 or i == 0:
            print(f"    [{i+1}/{total_matches}] LEFT:{left_wins} / RIGHT:{right_wins} / DRAW:{draws}")

    elapsed = time.time() - start_time

    print(f"    [완료] LEFT:{left_wins} WIN / RIGHT:{right_wins} WIN / DRAW:{draws} "
          f"({elapsed:.1f}초)")

    return PairwiseResult(
        left_profile=left_profile_id,
        right_profile=right_profile_id,
        total_matches=total_matches,
        left_wins=left_wins,
        right_wins=right_wins,
        draws=draws,
        left_win_rate=left_wins / total_matches * 100 if total_matches > 0 else 0,
        right_win_rate=right_wins / total_matches * 100 if total_matches > 0 else 0,
        draw_rate=draws / total_matches * 100 if total_matches > 0 else 0,
        avg_turns=total_turns_sum / total_matches if total_matches > 0 else 0
    )


def generate_cross_evaluation_matrix(results: Dict[Tuple[str, str], PairwiseResult]) -> Dict:
    """Cross Evaluation Matrix 생성"""
    profiles = set()
    for (left, right) in results.keys():
        profiles.add(left)
        profiles.add(right)
    profiles = sorted(profiles)

    matrix = {
        "profiles": profiles,
        "matrix": {},
        "stats": {}
    }

    for left in profiles:
        matrix["matrix"][left] = {}
        matrix["stats"][left] = {
            "total_matches": 0,
            "wins": 0,
            "draws": 0,
            "loses": 0,
            "win_rate": 0.0,
            "avg_turns": 0.0,
            "avg_move_pct": 0.0,
            "avg_wait_pct": 0.0,
            "avg_hq_distance": 0.0,
            "avg_stronghold_visit": 0.0,
        }

    for (left, right), result in results.items():
        outcome = "DRAW"
        if result.left_win_rate > result.right_win_rate:
            outcome = "WIN"
        elif result.left_win_rate < result.right_win_rate:
            outcome = "LOSE"

        matrix["matrix"][left][right] = {
            "outcome": outcome,
            "left_win_rate": round(result.left_win_rate, 1),
            "right_win_rate": round(result.right_win_rate, 1),
            "draw_rate": round(result.draw_rate, 1),
            "avg_turns": round(result.avg_turns, 1)
        }

        # 역방향도 추가 (right가 left를对战했을 때)
        reverse_outcome = "DRAW"
        if result.right_win_rate > result.left_win_rate:
            reverse_outcome = "WIN"
        elif result.right_win_rate < result.left_win_rate:
            reverse_outcome = "LOSE"

        matrix["matrix"][right][left] = {
            "outcome": reverse_outcome,
            "left_win_rate": round(result.right_win_rate, 1),
            "right_win_rate": round(result.left_win_rate, 1),
            "draw_rate": round(result.draw_rate, 1),
            "avg_turns": round(result.avg_turns, 1)
        }

        # Stats 누적
        matrix["stats"][left]["total_matches"] += result.total_matches
        matrix["stats"][left]["wins"] += result.left_wins
        matrix["stats"][left]["draws"] += result.draws
        matrix["stats"][left]["loses"] += result.right_wins

    # Win rate 계산
    for left in profiles:
        stats = matrix["stats"][left]
        if stats["total_matches"] > 0:
            stats["win_rate"] = round(stats["wins"] / stats["total_matches"] * 100, 1)

    return matrix


def print_matrix_report(matrix: Dict):
    """Cross Evaluation Matrix 출력"""
    profiles = matrix["profiles"]

    print("\n" + "=" * 80)
    print("CROSS EVALUATION MATRIX")
    print("=" * 80)

    # Header
    header = "        " + "".join(f"{p:>12}" for p in profiles)
    print(header)
    print("-" * (8 + 12 * len(profiles)))

    # Matrix
    for left in profiles:
        row = f"{left:>8}"
        for right in profiles:
            if left == right:
                row += f"{'DRAW':>12}"
            else:
                outcome = matrix["matrix"][left][right]["outcome"]
                row += f"{outcome:>12}"
        print(row)

    print("-" * (8 + 12 * len(profiles)))

    # Ranking
    print("\nAI RANKING (by Win Rate):")
    ranking = sorted(
        matrix["stats"].items(),
        key=lambda x: (x[1]["win_rate"], x[1]["wins"]),
        reverse=True
    )

    for i, (profile, stats) in enumerate(ranking, 1):
        print(f"  {i}. {profile}: {stats['win_rate']:.1f}% Win Rate "
              f"({stats['wins']}W / {stats['draws']}D / {stats['loses']}L)")


def list_profiles():
    """AI Profile 목록 표시"""
    print("\n" + "=" * 60)
    print("AI PROFILES")
    print("=" * 60)
    for pid, profile in AI_PROFILES.items():
        print(f"\n  [{pid}] {profile['name']}")
        print(f"    Description: {profile['description']}")
        print(f"    Exec: {profile['exec_left']}")
        if profile["env"]:
            print(f"    Env: {profile['env']}")
        else:
            print(f"    Env: (default)")


########################################
# Main
########################################
def main():
    parser = argparse.ArgumentParser(description="NYPC 2026 Cross Evaluation Framework")
    parser.add_argument("--list", action="store_true", help="List AI profiles")
    parser.add_argument("--verify", action="store_true", help="Lightweight verification (3 matches)")
    parser.add_argument("--profiles", nargs="+", help="Specific profiles to evaluate")
    parser.add_argument("--matches", type=int, default=TOTAL_MATCHES, help="Matches per pairing")
    args = parser.parse_args()

    if args.list:
        list_profiles()
        return

    print("=" * 80)
    print("NYPC 2026 - Cross Evaluation Framework")
    print("=" * 80)

    # 프로파일 선택
    if args.profiles:
        selected_profiles = args.profiles
    else:
        selected_profiles = list(AI_PROFILES.keys())

    print(f"Selected Profiles: {selected_profiles}")
    print(f"Matches per Pairing: {args.matches if args.verify else TOTAL_MATCHES}")

    # 출력 디렉토리
    eval_type = "verify" if args.verify else "full"
    output_dir = CROSS_EVAL_DIR / eval_type
    output_dir.mkdir(parents=True, exist_ok=True)

    # Profile 쌍 생성 (순서쌍만)
    pairs = []
    for left, right in combinations(selected_profiles, 2):
        pairs.append((left, right))

    print(f"\nTotal Pairings: {len(pairs)}")
    print(f"Total Matches: {len(pairs) * (args.matches if args.verify else TOTAL_MATCHES)}")
    print(f"Output Directory: {output_dir}")

    # Build 1회 실행
    print("\n[Build]")
    if not run_build():
        print("Build failed. Exiting.")
        return
    print("Build successful.")

    # Pairwise Evaluation 실행
    results = {}
    total_start = time.time()

    for i, (left, right) in enumerate(pairs, 1):
        print(f"\n[{i}/{len(pairs)}] Pairwise Evaluation")
        result = run_pairwise_evaluation(
            left, right,
            AI_PROFILES,
            output_dir,
            total_matches=args.matches if args.verify else TOTAL_MATCHES
        )
        results[(left, right)] = result

    total_elapsed = time.time() - total_start

    # Matrix 생성
    print("\n[Generating Cross Evaluation Matrix]")
    matrix = generate_cross_evaluation_matrix(results)

    # Report 저장
    report_path = output_dir / "cross_evaluation_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "total_matches": sum(r.total_matches for r in results.values()),
            "total_elapsed_sec": round(total_elapsed, 1),
            "profiles": selected_profiles,
            "matrix": matrix,
            "pairwise_results": {
                f"{left}_vs_{right}": {
                    "left_wins": r.left_wins,
                    "right_wins": r.right_wins,
                    "draws": r.draws,
                    "left_win_rate": r.left_win_rate,
                    "right_win_rate": r.right_win_rate,
                    "draw_rate": r.draw_rate,
                    "avg_turns": r.avg_turns
                }
                for (left, right), r in results.items()
            }
        }, f, indent=2)

    print(f"\n[OK] Report saved: {report_path}")

    # Matrix 출력
    print_matrix_report(matrix)

    print(f"\n[Complete] Total elapsed: {total_elapsed:.1f}초")


if __name__ == "__main__":
    main()
