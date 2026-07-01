#!/usr/bin/env python3
"""
Stronghold 방문 횟수 확인 - 간단 버전
"""
from pathlib import Path

def main():
    log_dir = Path("logs/baseline_benchmark")
    log_files = sorted(log_dir.glob("*.log"))[:3]  # 처음 3개만 확인
    
    for log_file in log_files:
        print(f"\n=== {log_file.name} ===")
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # 간단히 확인: chosen_moves가 0인지, chosen_upgrades가 0인지
        total_turns = 0
        moves_chosen = 0
        upgrades_chosen = 0
        
        for line in lines:
            if "# Debug" in line and ("chosen_moves" in line or "chosen_upgrades" in line):
                total_turns += 1
                if "chosen_moves\": 1" in line or "chosen_moves\": 2" in line or "chosen_moves\": 3" in line:
                    moves_chosen += 1
                if "chosen_upgrades\": 1" in line:
                    upgrades_chosen += 1
        
        print(f"- 총 턴 수: {total_turns}")
        print(f"- MOVE 선택 횟수: {moves_chosen}")
        print(f"- UPGRADE 선택 횟수: {upgrades_chosen}")
        
        if moves_chosen == 0:
            print("  → AI가 전혀 움직이지 않았습니다!")
        if upgrades_chosen == 0:
            print("  → AI가 한 번도 UPGRADE를 선택하지 않았습니다!")

if __name__ == "__main__":
    main()
