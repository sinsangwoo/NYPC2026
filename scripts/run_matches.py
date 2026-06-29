#!/usr/bin/env python3
"""
자동 경기 실행 스크립트
AI끼리 자동으로 경기를 실행하고 로그를 저장합니다.
"""

import subprocess
import time
from pathlib import Path

########################################
# Experiment Configuration
########################################
# 실험 설정 (여기서 쉽게 변경하세요!

# 플레이어 설정
PLAYER_LEFT = "python tools/testing-tool/sample-code.py"   # LEFT 플레이어 실행 명령
PLAYER_RIGHT = "python tools/testing-tool/sample-code.py"  # RIGHT 플레이어 실행 명령

# 경기 설정
TOTAL_MATCHES = 100  # 총 경기 수
START_SEED = 1      # 시작 시드 (각 경기마다 1씩 증가
MATCH_TIMEOUT = 300   # 개별 경기 타임아웃 (초)

# 로그 설정
LOGS_DIR = "logs/raw"  # 로그 저장 폴더
########################################


def main():
    # 프로젝트 루트 경로
    project_root = Path(__file__).parent.parent
    
    # 경로 설정
    testing_tool = project_root / "tools" / "testing-tool" / "testing-tool.py"
    logs_dir = project_root / LOGS_DIR
    
    # logs/raw 디렉토리가 없으면 생성
    logs_dir.mkdir(parents=True, exist_ok=True)
    
    success_count = 0
    failure_count = 0
    
    start_time = time.time()
    
    print(f"=== 자동 경기 실행 시작 ===")
    print(f"LEFT 플레이어: {PLAYER_LEFT}")
    print(f"RIGHT 플레이어: {PLAYER_RIGHT}")
    print(f"총 경기 수: {TOTAL_MATCHES}")
    print(f"시작 시드: {START_SEED}")
    print(f"로그 저장 경로: {logs_dir}")
    print("-" * 50)
    
    for i in range(TOTAL_MATCHES):
        match_num = i + 1
        seed = START_SEED + i
        
        # 로그 파일명 생성 (game_0001.log 형식)
        log_filename = f"game_{match_num:04d}.log"
        log_filepath = logs_dir / log_filename
        
        # 기존 로그가 있으면 건너뛰기
        if log_filepath.exists():
            print(f"경기 {match_num}/{TOTAL_MATCHES}: 로그 파일이 이미 존재하므로 건너뜁니다.")
            success_count += 1
            continue
        
        print(f"경기 {match_num}/{TOTAL_MATCHES}: 실행 중... (시드: {seed})")
        
        try:
            # testing-tool.py 실행
            # 명령어: python testing-tool.py --seed {seed} --exec1 {PLAYER_LEFT} --exec2 {PLAYER_RIGHT} --log {log_filepath}
            cmd = [
                "python",
                str(testing_tool),
                "--seed", str(seed),
                "--exec1", PLAYER_LEFT,
                "--exec2", PLAYER_RIGHT,
                "--log", str(log_filepath)
            ]
            
            # 프로세스 실행 (개별 경기 타임아웃 처리, 전체 실행은 계속됨)
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=MATCH_TIMEOUT,
                cwd=project_root  # 프로젝트 루트에서 실행
            )
            
            if result.returncode == 0:
                print(f"경기 {match_num}/{TOTAL_MATCHES}: 성공!")
                success_count += 1
            else:
                print(f"경기 {match_num}/{TOTAL_MATCHES}: 실패 (종료 코드: {result.returncode})")
                print(f"  stderr: {result.stderr[:200]}...")
                failure_count += 1
                
        except subprocess.TimeoutExpired:
            print(f"경기 {match_num}/{TOTAL_MATCHES}: 타임아웃 ({MATCH_TIMEOUT}초 초과)")
            failure_count += 1
        except Exception as e:
            print(f"경기 {match_num}/{TOTAL_MATCHES}: 오류 발생 - {e}")
            failure_count += 1
    
    # 전체 실행 시간 계산
    end_time = time.time()
    elapsed_time = end_time - start_time
    
    # 결과 출력
    print("-" * 50)
    print(f"=== 자동 경기 실행 완료 ===")
    print(f"전체 실행 시간: {elapsed_time:.2f}초 ({elapsed_time/60:.2f}분)")
    print(f"성공 경기 수: {success_count}")
    print(f"실패 경기 수: {failure_count}")


if __name__ == "__main__":
    main()
