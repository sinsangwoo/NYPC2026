#!/usr/bin/env python3
"""
Stronghold 방문 횟수 분석 스크립트
Stronghold 위에 아군 Warrior가 존재했던 턴 수를 세어봅니다.
"""

import json
from pathlib import Path


def analyze_log(log_path: Path):
    """단일 로그 파일 분석"""
    strongholds = []
    total_turns_with_ally_on_stronghold = 0
    current_turn = 0
    my_side = None  # LEFT 또는 RIGHT

    with open(log_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # 1. Stronghold 목록과 내 side 찾기
    for i, line in enumerate(lines):
        if line.startswith("STRONGHOLDS"):
            # Stronghold 목록 파싱
            parts = line.strip().split()
            strongholds = list(map(int, parts[1:]))
            print(f"Stronghold 목록: {strongholds}")
        
        if "TURN 1 RESULT" in line:
            # 내 side 찾기 (첫 번째 턴 결과에서 COMMAND가 있었던 쪽)
            for j in range(i-5, i):
                if j >=0 and "COMMAND LEFT" in lines[j]:
                    my_side = "LEFT"
                    break
                if j >=0 and "COMMAND RIGHT" in lines[j]:
                    my_side = "RIGHT"
                    break
            print(f"나의 Side: {my_side}")
            break

    if not strongholds:
        print("STRONGHOLDS를 찾을 수 없습니다!")
        return

    # 2. 각 턴마다 아군 Warrior 위치 확인
    i = 0
    while i < len(lines):
        line = lines[i]
        
        if line.startswith("TURN") and "RESULT" in line:
            current_turn = int(line.split()[1])
            # 이제 다음 TURN 또는 END TURN 전까지 Warrior 위치 찾기
            i +=1
            warriors_on_stronghold = 0
            
            while i < len(lines) and not lines[i].startswith("TURN") and not lines[i].startswith("END TURN"):
                # Warrior 위치 찾기 (예: "A1->2" 또는 "B1->78")
                # RESULT 라인에 움직인 Warrior 정보가 있음
                # 또는 그냥 전체 라인에서 Warrior ID 찾기
                # 실제로는, TURN X RESULT 다음에 오는 라인들에 Warrior 위치가 표시됨
                # 형식: "A1 2" 또는 "B1 78" 같은 식으로 있음?
                # 아니면 "MOVE A1 2" 라인?
                # 로그를 다시 보면, "TURN X RESULT" 다음에 "MOVE A1 16" 이런 식으로 있음
                # 그리고 나서 "END TURN X"가 나옴
                
                # 간단히, 이 턴에 아군 Warrior가 Stronghold에 있는지 확인
                # my_side가 LEFT이면 A로 시작하는 Warrior, RIGHT이면 B로 시작하는 Warrior
                for stronghold in strongholds:
                    # 해당 Stronghold에 아군 Warrior가 있는지 확인
                    # 라인에서 "A{num} {stronghold}" 또는 "B{num} {stronghold}" 찾기
                    prefix = "A" if my_side == "LEFT" else "B"
                    if f" {stronghold}" in line and prefix in line:
                        warriors_on_stronghold +=1
                        break
                
                i +=1
            
            if warriors_on_stronghold >0:
                total_turns_with_ally_on_stronghold +=1
                # print(f"Turn {current_turn}: {warriors_on_stronghold}명의 아군 Warrior가 Stronghold에 있음!")
        
        else:
            i +=1
    
    print(f"총 Stronghold 방문 턴 수: {total_turns_with_ally_on_stronghold}")
    return total_turns_with_ally_on_stronghold


def main():
    log_dir = Path("logs/baseline_benchmark")
    log_files = sorted(log_dir.glob("*.log"))
    
    print(f"총 {len(log_files)}개의 로그 파일 분석 시작...\n")
    
    total_all_logs = 0
    for i, log_file in enumerate(log_files[:5]):  # 처음 5개만 분석해도 충분함
        print(f"=== {log_file.name} 분석 ===")
        turns = analyze_log(log_file)
        total_all_logs += turns
        print()
    
    print(f"\n전체 로그에서 Stronghold 방문 총 턴 수: {total_all_logs}")


if __name__ == "__main__":
    main()
