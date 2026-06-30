# 🎮 NYPC 2026 MASTER TRACK

우리 팀의 **NYPC 2026 마스터 트랙** 참가 프로젝트입니다! NEXT NATION 게임의 AI를 개발하고 분석하는 공간이에요.

---

## 📌 프로젝트 개요 (초보자도 이해가 쉬워요!)

**NEXT NATION**은 두 플레이어가 턴을 번갈아가며 전략을 펼치는 전쟁 게임이에요. 우리 팀은 이 게임에서 이기는 **자동 AI**를 만드는 게 목표입니다!

우리가 할 일:
1. 🏃 AI끼리 자동으로 경기 시키기
2. 📊 경기 결과 분석하기
3. 💡 분석 결과로 AI 강화하기

---

## 📁 폴더 구조 (뭐가 어디에 있나?)

```
NYPC2026/
├── docs/             📚 프로젝트 문서 (게임 규칙, 개발 방법 등)
├── logs/             📝 게임 로그와 분석 결과
│   ├── raw/          🎮 원본 게임 로그 파일들 (파일이 많아서 git에 안 올림!)
│   └── analysis/     📊 분석 결과 파일들
├── scripts/          🔧 유용한 스크립트들
│   ├── run_matches.py    🎯 자동으로 경기 실행하는 스크립트
│   └── analyze_logs.py   🔍 경기 로그 분석하는 스크립트
├── src/              💻 우리가 개발한 AI 소스 코드
├── tools/            🛠️ 대회에서 제공된 도구들
│   └── testing-tool/  🎮 게임을 실제로 돌리는 툴
├── .gitignore        🚫 Git이 무시할 파일들
└── README.md         📖 이 파일!
```

---

## 🚀 빠른 시작 (5분만에 시작하기!)

### 1. 🎮 자동 경기 실행하기

Sample AI끼리 **100경기** 자동으로 돌리고 로그를 저장하려면:

```bash
# 프로젝트 폴더 (NYPC2026/)에서 실행해요!
python scripts/run_matches.py
```

### 2. ⚙️ 경기 설정 바꾸기

`scripts/run_matches.py` 파일의 맨 위에 **Experiment Configuration** 부분에서 쉽게 바꿀 수 있어요:

```python
# 플레이어 바꾸기 (우리 AI vs Sample AI)
PLAYER_LEFT = "python submission.py"    # 우리가 만든 AI
PLAYER_RIGHT = "python tools/testing-tool/sample-code.py"  # 대회에서 준 샘플 AI

# 경기 수 바꾸기
TOTAL_MATCHES = 50  # 50경기만 실행
```

### 3. 📊 경기 로그 분석하기

경기 결과를 **자동으로 분석**하려면:

```bash
# 프로젝트 폴더에서 실행
python scripts/analyze_logs.py
```

이렇게 하면:
- 각 경기별로 상세 분석 파일이 `logs/analysis/match_XXXX/`에 생깁니다!
- 전체 경기의 요약이 `logs/analysis/features.csv`에 저장됩니다.

---

## ✨ 주요 기능

| 기능 | 설명 |
|------|------|
| 🎯 **자동 경기 실행** | 여러 경기를 한 번에 돌리고 로그 자동 저장 |
| ⚙️ **설정 쉬움** | 플레이어, 경기 수, 시드 등 한 곳에서 관리 |
| 🔍 **로그 분석** | 경기 결과 자동으로 분석하고 통계 보여줌 |
| ⏱️ **타임아웃 처리** | 하나의 경기가 오래 걸려도 전체가 멈추지 않음 |
| ⏭️ **중복 실행 방지** | 이미 돌린 경기는 다시 안 돌림 |

---

## 📚 게임 규칙과 개발 방법

자세한 건 `docs/` 폴더에 있는 문서를 보세요!
- `01_PROJECT_CONTEXT.md`: 프로젝트 전체 설명
- `02_DEVELOPMENT_GUIDE.md`: 개발하는 방법 가이드
- `03_GAME_RULES.md`: 게임 규칙 상세

---

## 🐙 Git 사용법 (초보자도 따라할 수 있어요!)

Git으로 변경 사항을 관리하고 GitHub에 올리는 방법이에요:

```bash
# 1. 변경된 파일 확인하기
git status

# 2. 변경된 파일 추가하기 (모든 파일)
git add .

# 3. 변경 내용 저장하기 (커밋)
git commit -m "여기에 변경 내용 적어요! 예: 로그 분석 스크립트 추가"

# 4. GitHub에 올리기 (푸시)
git push
```

---

## 💡 처음 오신 팀원분들!

1. 먼저 이 README 파일을 다 읽어보세요!
2. `docs/01_PROJECT_CONTEXT.md`도 읽어보면 프로젝트가 더 이해가 돼요.
3. `scripts/run_matches.py`로 한 번 경기를 돌려보세요!
4. 궁금한 게 있으면 팀 카톡방에 물어보세요 😊
