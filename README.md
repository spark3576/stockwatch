# 📊 StockWatch

다국가(KR/US/JP/UK/DE) 주식 분석 + AI 시그널 + 텔레그램 자동 리포트 + 카드 아카이빙 플랫폼.

> ⚠️ 본 결과물은 정보 제공 목적이며 투자 권유가 아닙니다.

---

## 🪜 빌드 단계 (Phase)

- [x] **Phase 1 — 뼈대**: 데이터 수집 + 차트 시그널 + 텔레그램 수동 분석
- [ ] **Phase 2 — 자동 리포트**: 스크리닝 + 매일/이벤트 알림
- [ ] **Phase 3 — AI 시그널**: 8개 종합 (Opus 4.7)
- [ ] **Phase 4 — 대시보드**: 카드 아카이빙 (Next.js)
- [ ] **Phase 5 — 트래킹**: 시계열 + 적중률
- [ ] **Phase 6+ — 확장**: 12개 추가 아이디어

---

## 🌍 지원 시장

| 시장 | 코드 예시 | 데이터 소스 |
|---|---|---|
| 🇰🇷 한국 (KOSPI/KOSDAQ) | `005930` (삼성전자) | pykrx + yfinance |
| 🇺🇸 미국 | `AAPL` | yfinance |
| 🇯🇵 일본 (TSE) | `7203.T` (도요타) | yfinance |
| 🇬🇧 영국 (LSE) | `BARC.L` | yfinance |
| 🇩🇪 독일 (Xetra) | `SAP.DE` | yfinance |

---

## 🚀 빠른 시작

```bash
# 1. 가상환경
python3 -m venv .venv
source .venv/bin/activate

# 2. 의존성
pip install -r requirements.txt

# 3. 환경변수 설정
cp .env.example .env
# .env 편집 (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)

# 4. DB 초기화
python main.py init-db

# 5. 종목 분석 (수동)
python main.py analyze 005930          # 삼성전자 (KR)
python main.py analyze AAPL            # 애플 (US)
python main.py analyze 7203.T          # 도요타 (JP)

# 6. 텔레그램 봇 테스트
python main.py test-telegram
```

---

## 📁 폴더 구조

```
stockwatch/
├── main.py                    # CLI 진입점
├── requirements.txt
├── config.yaml                # 설정
├── .env                       # 비밀 (gitignored)
├── src/
│   ├── collectors/            # 데이터 수집 (KR, 글로벌)
│   ├── signals/               # 시그널 (Phase 1: 차트 시그널)
│   ├── db/                    # SQLite 매니저
│   ├── notifier/              # 텔레그램
│   ├── analyzer/              # AI 분석 (Phase 3+)
│   └── utils/
├── data/                      # SQLite DB
├── logs/
├── tests/
└── scripts/                   # 유틸 스크립트
```

---

## 🤖 AI 모델 전략

| 작업 | 모델 |
|---|---|
| 팩트 헌터 / 종합 카드 / Why 엔진 / 리스크 | **Opus 4.7** |
| 단순 요약·분류 | Sonnet 4.6 |
| 임베딩·태깅 | Haiku 4.5 |

> Phase 1~2는 AI 호출 없음 (순수 결정론적 신호)

---

## 🔗 연관 프로젝트

- `../trend-stock-scanner/` — KR 트렌드+거래량 스크리너 (모듈 일부 재사용)
