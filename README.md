# NYPC 2026 MASTER TRACK

우리 팀의 NYPC 2026 MASTER TRACK 참가 프로젝트입니다. NEXT NATION 게임 AI를 개발합니다.

## 프로젝트 개요

NEXT NATION은 두 플레이어가 턴제로 전략을 펼치는 게임입니다. 우리는 자동으로 경기를 실행하고 분석할 수 있는 인프라를 구축한 뒤, 최강의 게임 AI를 개발하는 것을 목표로 합니다.

## 폴더 구조

```
NYPC2026/
├── docs/             # 프로젝트 문서 (게임 규칙, 개발 가이드 등)
├── logs/             # 게임 로그와 분석 결과
│   ├── raw/          # 원본 게임 로그 (git에 올리지 않음)
│   └── analysis/     # 분석 결과
├── scripts/          # 유용한 스크립트들
│   └── run_matches.py  # 자동 경기 실행 스크립트
├── src/              # 우리가 개발한 AI 소스 코드
├── tools/            # 대회에서 제공된 도구들
│   └── testing-tool/  # 게임 테스팅 툴
├── .gitignore        # Git 무시 파일
└── README.md         # 이 파일
```

## 빠른 시작

### 1. 자동 경기 실행하기

Sample AI끼리 100경기 자동으로 실행하고 로그를 저장하려면:

```bash
# 프로젝트 루트에서 실행
python scripts/run_matches.py
```

### 2. 경기 설정 변경하기

`scripts/run_matches.py` 파일의 상단 **Experiment Configuration** 섹션에서 쉽게 변경할 수 있습니다:

```python
# 플레이어 변경
PLAYER_LEFT = "python submission.py"  # 우리 AI
PLAYER_RIGHT = "python tools/testing-tool/sample-code.py"  # Sample AI

# 경기 수 변경
TOTAL_MATCHES = 50  # 50경기만 실행
```

## 주요 기능

- ✅ **자동 경기 실행**: 여러 경기를 한 번에 실행하고 로그 저장
- ✅ **실험 설정 용이**: 플레이어, 경기 수, 시드 등을 한 곳에서 관리
- ✅ **타임아웃 처리**: 개별 경기 타임아웃이 전체 실행을 막지 않음
- ✅ **기존 로그 건너뛰기**: 이미 실행된 경기는 다시 실행하지 않음

## 게임 규칙

자세한 게임 규칙은 `docs/` 폴더의 문서들을 참고하세요:
- `01_PROJECT_CONTEXT.md`: 프로젝트 개요
- `03_GAME_RULES.md`: 게임 규칙 상세

## 개발 가이드

`docs/02_DEVELOPMENT_GUIDE.md`를 참고하세요.

## Git 사용법

```bash
# 변경 사항 확인
git status

# 변경 사항 추가
git add .

# 커밋
git commit -m "커밋 메시지"

# 푸시
git push
```
