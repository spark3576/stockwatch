"""기술적 지표 한줄 해설 (텔레그램·콘솔용 미니 백과사전).

모든 시그널·지표가 Investopedia·교과서 기준의 한줄 설명 + 임계값을 가짐.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GlossaryItem:
    key: str            # 매칭용 키 (체크 이름의 핵심 부분)
    title: str          # 표시명 (예: "MACD")
    one_liner: str      # 1줄 요약
    detail: str         # 상세 (CLI 명령어용)


# 키는 check_name 의 일부 substring 매칭에 쓰임 (소문자/대소문자 무관)
GLOSSARY: list[GlossaryItem] = [
    GlossaryItem(
        key="이평선",
        title="이동평균선 (MA)",
        one_liner="N일 평균값. 종가가 위면 상승추세, 아래면 하락추세.",
        detail=(
            "Moving Average. 5/20일은 단기, 60/120/200일은 장기. "
            "종가가 이평선 위 = 매수세 우위, 아래 = 매도세 우위로 해석.\n"
            "정배열(짧은 MA > 긴 MA) = 상승추세 / 역배열 = 하락추세."
        ),
    ),
    GlossaryItem(
        key="MACD",
        title="MACD",
        one_liner="12·26일 EMA 차이의 추세선. 히스토그램 +면 강세, -면 약세.",
        detail=(
            "Moving Average Convergence Divergence. "
            "MACD = EMA(12) - EMA(26), Signal = EMA(MACD,9), Histogram = MACD - Signal.\n"
            "골든크로스(MACD↑Signal) = 매수, 데드크로스 = 매도. "
            "히스토그램 양→음 전환은 추세 둔화 신호."
        ),
    ),
    GlossaryItem(
        key="ADX",
        title="ADX",
        one_liner="추세 강도 지표 (방향 무관). 25+ 강한 추세, 20- 횡보.",
        detail=(
            "Average Directional Index. 0~100 사이 값. "
            "25 이상이면 강한 추세, 20 이하면 추세 없음(횡보장).\n"
            "추세 방향은 별도로 봐야 함 (예: 종가 vs 이평선)."
        ),
    ),
    GlossaryItem(
        key="RSI",
        title="RSI",
        one_liner="14일 모멘텀. 70+ 과매수(조정 가능), 30- 과매도(반등 가능).",
        detail=(
            "Relative Strength Index. 0~100 사이. "
            "70 위면 과매수(차익실현 매물 우려), 30 아래면 과매도(반등 가능). "
            "50 위는 매수 우위, 50 아래는 매도 우위."
        ),
    ),
    GlossaryItem(
        key="볼린저",
        title="볼린저 밴드 %B",
        one_liner="20일 평균±2표준편차 밴드 내 위치. 1=상단, 0=하단, 0.5=중간.",
        detail=(
            "Bollinger Bands %B. 가격이 밴드 안에서 어디 있는지 0~1 정규화.\n"
            "%B > 1 = 상단 돌파(과열), %B < 0 = 하단 이탈(과매도).\n"
            "밴드 폭(bandwidth) 좁아지면 변동성 수축 → 큰 움직임 임박."
        ),
    ),
    GlossaryItem(
        key="스토캐스틱",
        title="스토캐스틱",
        one_liner="14일 고저 대비 종가 위치. K>D 골든, K<D 데드. 80+ 과매수.",
        detail=(
            "Stochastic Oscillator. %K = 종가의 14일 고저 범위 내 위치. "
            "%D = %K의 3일 평균(시그널선).\n"
            "%K > %D 골든크로스 = 매수, 80+ 과매수, 20- 과매도."
        ),
    ),
    GlossaryItem(
        key="Williams",
        title="Williams %R",
        one_liner="14일 고가 대비 현재가 거리. -20+ 과매수, -80- 과매도.",
        detail=(
            "Williams %R. -100 ~ 0 사이. "
            "-20 위 = 과매수, -80 아래 = 과매도. RSI와 비슷하나 반응이 더 빠름."
        ),
    ),
    GlossaryItem(
        key="CCI",
        title="CCI",
        one_liner="가격이 평균에서 얼마나 벗어났나. ±100 밖이면 강한 신호.",
        detail=(
            "Commodity Channel Index. (대표가격 - 평균) / (0.015 × 평균편차).\n"
            "+100 위 = 강한 상승 모멘텀, -100 아래 = 강한 하락 모멘텀.\n"
            "RSI보다 변동성이 커 단기 매매에 유리."
        ),
    ),
    GlossaryItem(
        key="MFI",
        title="MFI (자금흐름)",
        one_liner="거래량 가중 RSI. 80+ 자금 과유입, 20- 자금 과유출.",
        detail=(
            "Money Flow Index. RSI에 거래량을 가중한 버전.\n"
            "기관·외인 자금 유입 강도를 추정. 80+ 매수 과열, 20- 매도 과열."
        ),
    ),
    GlossaryItem(
        key="일목",
        title="일목균형표",
        one_liner="구름대 위 = 상승, 아래 = 하락, 안 = 박스권.",
        detail=(
            "Ichimoku Cloud. 5개 선(전환선/기준선/선행스팬1·2/후행스팬)으로 추세·지지·저항 종합 판단.\n"
            "구름대(선행스팬1·2 사이) 위에서 거래 = 상승추세, 아래 = 하락추세, "
            "구름 안 = 방향성 불분명 박스권."
        ),
    ),
    GlossaryItem(
        key="OBV",
        title="OBV (누적거래량)",
        one_liner="종가↑일 거래량은 +, 종가↓일은 - 누적. 가격보다 먼저 움직이는 경향.",
        detail=(
            "On-Balance Volume. 종가가 오른 날의 거래량은 더하고, 떨어진 날은 뺌(누적).\n"
            "OBV가 가격보다 먼저 움직이면 선행지표로 작동. "
            "OBV↑ + 가격횡보 = 매집 의심, OBV↓ + 가격횡보 = 분배 의심."
        ),
    ),
    GlossaryItem(
        key="거래량",
        title="거래량",
        one_liner="N일 평균 대비 비율. 1.5x↑ 급증, 0.6x↓ 위축.",
        detail=(
            "거래량은 가격 신호의 신뢰도. 거래량 동반한 돌파 = 진짜 돌파.\n"
            "거래량 없는 돌파 = 페이크아웃 위험."
        ),
    ),
    GlossaryItem(
        key="망치",
        title="망치 / 슈팅스타",
        one_liner="긴 꼬리 + 작은 몸통 캔들. 추세 끝에서 반전 신호.",
        detail=(
            "망치(Hammer) = 긴 아래꼬리, 하락추세 끝에서 매수 반전.\n"
            "슈팅스타(Shooting Star) = 긴 위꼬리, 상승추세 끝에서 매도 반전."
        ),
    ),
    GlossaryItem(
        key="도지",
        title="도지 캔들",
        one_liner="시가 ≈ 종가. 매수·매도 균형 → 추세 전환점일 수 있음.",
        detail=(
            "Doji. 시가와 종가가 거의 같음. 시장의 의사결정 부재.\n"
            "추세 끝에서 도지 = 반전 가능성. 횡보장에서 도지 = 의미 적음."
        ),
    ),
    GlossaryItem(
        key="엔걸핑",
        title="엔걸핑 (감싸기)",
        one_liner="다음 봉이 전 봉을 완전히 감쌈. 강한 추세 전환.",
        detail=(
            "Engulfing Pattern. 강세 엔걸핑 = 큰 양봉이 직전 음봉을 감쌈 → 매수.\n"
            "약세 엔걸핑 = 큰 음봉이 직전 양봉을 감쌈 → 매도. 추세 끝에 더 강력."
        ),
    ),
    GlossaryItem(
        key="모닝",
        title="모닝/이브닝 스타",
        one_liner="3봉 패턴. 큰 봉 → 작은 봉 → 큰 반대봉. 강한 반전.",
        detail=(
            "Morning Star = 음봉(큰)→ 작은 봉(갭다운)→ 양봉(큰, 첫봉 절반 회복).\n"
            "Evening Star = 그 반대. 하락→상승, 상승→하락 강한 반전 신호."
        ),
    ),
    GlossaryItem(
        key="크로스",
        title="이평선·MACD 교차",
        one_liner="짧은 선이 긴 선 상향 돌파 = 골든, 하향 = 데드.",
        detail=(
            "Golden Cross = 단기선이 장기선 상향 돌파(매수 신호).\n"
            "Death Cross = 단기선이 장기선 하향 돌파(매도 신호).\n"
            "5/20, 20/60, 50/200, MACD/Signal 등 다양한 조합 사용."
        ),
    ),
    GlossaryItem(
        key="다이버전스",
        title="가격-RSI 다이버전스",
        one_liner="가격↑인데 RSI↓ = 약세 다이버전스. 가격↓인데 RSI↑ = 강세.",
        detail=(
            "Divergence. 가격과 모멘텀 지표(RSI 등)가 반대로 움직이는 것.\n"
            "강세 다이버전스 = 가격은 신저가지만 RSI는 더 높음 → 하락 둔화 = 매수 신호.\n"
            "약세 다이버전스 = 가격은 신고가지만 RSI는 더 낮음 → 상승 둔화 = 매도 신호."
        ),
    ),
    GlossaryItem(
        key="52주",
        title="52주 신고가/신저가",
        one_liner="1년 최고/최저가. 신고가 갱신 = 강한 상승, 신저가 = 강한 하락.",
        detail=(
            "52-Week High/Low. 신고가 돌파 = 모멘텀 강세, 매수세 압도.\n"
            "신저가 = 모멘텀 약세. 거래량 동반 신고가 돌파가 가장 신뢰성 높은 매수 신호."
        ),
    ),
    GlossaryItem(
        key="박스권",
        title="박스권 (Range)",
        one_liner="N일 고저 범위. 상단 돌파 = 매수, 하단 이탈 = 매도.",
        detail=(
            "최근 N일 고가·저가가 만드는 박스. 박스 안에서는 매매 의미 적음.\n"
            "거래량 동반한 박스 상단 돌파 = 강력한 매수 신호."
        ),
    ),
    GlossaryItem(
        key="200일선",
        title="200일선",
        one_liner="장기 추세선. 위 = 강세장, 아래 = 약세장.",
        detail=(
            "200일 단순 이동평균. 기관·헤지펀드의 장기 추세 판단 기준.\n"
            "200일선 위 + 200일선 상승 추세 = 황소장 / 아래 = 곰장."
        ),
    ),
    GlossaryItem(
        key="갭",
        title="갭상승 / 갭하락",
        one_liner="시가가 전일 고가/저가를 벗어나서 시작. 강한 모멘텀.",
        detail=(
            "Gap Up = 시가 > 전일 고가 (호재 반응 또는 매수 폭발).\n"
            "Gap Down = 시가 < 전일 저가 (악재 또는 매도 폭주).\n"
            "갭 후 첫 봉 마감 위치가 중요(메우면 페이크, 유지하면 추세)."
        ),
    ),
    # ──── 퀀트 팩터 (Phase 1B) ────
    GlossaryItem(
        key="수익률 vs 시장",
        title="기간별 수익률 vs 시장",
        one_liner="N개월 수익률을 시장 지수(KOSPI/S&P/Nikkei 등)와 비교한 알파.",
        detail=(
            "주식 수익률 - 시장 수익률 = 알파(α). 양수면 시장 초과수익, 음수면 시장 미달.\n"
            "1M/3M/6M/12M 모두 양수면 강한 모멘텀. "
            "12M 음수 + 1M 양수 = 바닥 다지고 상승 전환 가능."
        ),
    ),
    GlossaryItem(
        key="모멘텀 종합",
        title="모멘텀 종합 점수",
        one_liner="1M·3M·6M·12M 수익률을 가중평균. 장기 비중↑ (각 0.1·0.2·0.3·0.4).",
        detail=(
            "Cross-sectional Momentum. 단기 노이즈를 줄이기 위해 장기 가중. "
            "+10% 이상 = 강한 상승 모멘텀, -10% 이하 = 약세 지속."
        ),
    ),
    GlossaryItem(
        key="베타",
        title="베타 (β)",
        one_liner="시장 대비 변동성. 1=시장과 동조, 1.3+ 공격형, 0.7- 방어형.",
        detail=(
            "Beta = Cov(주식수익률, 시장수익률) / Var(시장수익률).\n"
            "β=1 시장과 같은 폭, β=1.5 시장 +1% → 주식 +1.5%, β=0.5 시장 +1% → 주식 +0.5%.\n"
            "음수 베타는 시장 반대로 움직임 (희귀, 대표적으로 금/달러 자산).\n"
            "강세장엔 베타 높을수록 유리, 약세장엔 베타 낮을수록 안전."
        ),
    ),
    GlossaryItem(
        key="변동성",
        title="연환산 변동성 (Volatility)",
        one_liner="일수익률 표준편차 × √252. 30%=중간, 50%+ 위험.",
        detail=(
            "Annualized Volatility. 일수익률의 표준편차를 연 단위로 환산.\n"
            "한국 대형주 평균 25~35%, 성장주 40~60%, 코인 80%+.\n"
            "60일 단기 변동성이 1년 평균보다 30%↑면 위험 증가, 30%↓면 안정화."
        ),
    ),
    GlossaryItem(
        key="샤프",
        title="샤프 비율 (Sharpe Ratio)",
        one_liner="(연수익 - 무위험이자) / 변동성. 1.0+ 우수, 0- 손실.",
        detail=(
            "Sharpe Ratio. 위험 1단위당 초과수익률.\n"
            "0.5~1.0 = 평균, 1.0~2.0 = 우수, 2.0+ 매우 우수, 0 미만 = 위험만 부담하고 손실.\n"
            "헤지펀드 평균 약 0.7. 이 도구는 무위험 이자율을 시장별로 다르게 사용 (KR 3.5%, US 4.5%)."
        ),
    ),
    GlossaryItem(
        key="MDD",
        title="최대 낙폭 (MDD)",
        one_liner="고점 대비 최대 하락폭. -10% 이내 양호, -25% 초과 위험.",
        detail=(
            "Maximum Drawdown. 1년간 고점에서 가장 깊이 빠진 폭(%).\n"
            "투자자가 가장 견뎌야 할 손실 크기. -50% MDD = 절반 토막난 적 있다는 뜻.\n"
            "샤프와 함께 보면 위험·수익 균형 종합 판단 가능."
        ),
    ),
    GlossaryItem(
        key="VaR",
        title="VaR (Value at Risk)",
        one_liner="하루 최악의 5%일 평균 손실. -2% 이내 양호, -4% 초과 변동성↑.",
        detail=(
            "Value at Risk 95%. 일별 수익률 분포의 5분위 (하위 5%).\n"
            "예: VaR 95% = -3% → 100일 중 5일은 하루에 3% 이상 빠짐.\n"
            "정규분포 가정 안 함 (실제 분포의 분위수 사용 — fat tail 반영)."
        ),
    ),
    # ──── 재무 분석 (Phase 1C) ────
    GlossaryItem(
        key="PER",
        title="PER (주가수익비율)",
        one_liner="시가총액 ÷ 당기순이익. 10- 저평가, 20+ 다소 고평가.",
        detail=(
            "Price Earnings Ratio = 주가 ÷ EPS = 시가총액 ÷ 순이익.\n"
            "낮으면 이익 대비 싸게 거래 = 저평가, 높으면 고평가 또는 고성장 기대.\n"
            "한국 시장 평균 약 12, 미국 S&P500 약 22, 성장주 30+ 흔함.\n"
            "TTM(최근 4분기) vs Forward(향후 12개월 추정) 둘 다 봐야 함."
        ),
    ),
    GlossaryItem(
        key="Forward PER",
        title="Forward PER",
        one_liner="향후 12개월 예상 EPS 기준 PER. TTM보다 낮으면 이익 성장 예상.",
        detail=(
            "애널리스트 컨센서스 EPS 추정치를 사용. "
            "TTM PER > Forward PER이면 이익이 성장한다는 뜻 (싸지는 효과).\n"
            "TTM < Forward면 이익이 감소한다는 뜻 (비싸지는 효과)."
        ),
    ),
    GlossaryItem(
        key="PBR",
        title="PBR (주가순자산비율)",
        one_liner="시가총액 ÷ 자기자본. 1.0 미만 = 청산가치 이하 (이론상 저평가).",
        detail=(
            "Price-to-Book Ratio. PBR < 1 = 시가총액이 자기자본보다 작음.\n"
            "은행·보험 등 자산집약 업종에 특히 유용. 기술주는 PBR이 높아도 정상.\n"
            "한국 시장 평균 약 1.0, 미국 S&P500 약 4.0."
        ),
    ),
    GlossaryItem(
        key="PSR",
        title="PSR (주가매출비율)",
        one_liner="시가총액 ÷ 매출. 적자 기업도 평가 가능. 3+ 다소 고평가.",
        detail=(
            "Price-to-Sales Ratio. 이익이 0이거나 적자라 PER 못 쓸 때 유용.\n"
            "성장주·고PER 종목 평가용. 일반 기업 1~3, 성장주 5~10.\n"
            "수익성이 같다면 PSR 낮을수록 매력."
        ),
    ),
    GlossaryItem(
        key="EV/EBITDA",
        title="EV/EBITDA",
        one_liner="기업가치 ÷ 영업현금흐름. 8- 저평가, 15+ 다소 고평가.",
        detail=(
            "Enterprise Value / EBITDA. EV = 시가총액 + 부채 - 현금.\n"
            "PER보다 부채 영향까지 반영해 더 정확. M&A 평가에서 표준.\n"
            "EBITDA = 이자·세금·감가상각 전 이익 (영업현금흐름 근사)."
        ),
    ),
    GlossaryItem(
        key="ROE",
        title="ROE (자기자본수익률)",
        one_liner="순이익 ÷ 자기자본. 15+ 우수, 워런 버핏 기준 20+.",
        detail=(
            "Return on Equity. 주주 자본으로 얼마나 이익 냈는가.\n"
            "최고의 기업 지표 중 하나. 5년 연속 ROE 15+면 우수 기업.\n"
            "단, 부채 많으면 ROE도 부풀려짐 → ROIC 함께 봐야 정확."
        ),
    ),
    GlossaryItem(
        key="영업이익률",
        title="영업이익률 (Operating Margin)",
        one_liner="영업이익 ÷ 매출. 본업의 효율. 20+ 우수, 5- 부진.",
        detail=(
            "Operating Margin = (매출 - 매출원가 - 판관비) ÷ 매출.\n"
            "본업의 마진. 산업별 차이 큼 (소프트웨어 30%+, 유통 5% 미만).\n"
            "동종업계 비교가 핵심."
        ),
    ),
    GlossaryItem(
        key="부채비율",
        title="부채비율 (D/E)",
        one_liner="총부채 ÷ 자기자본. 50- 안전, 200+ 위험.",
        detail=(
            "Debt-to-Equity Ratio. 자본 대비 부채 비율(%).\n"
            "50% = 자본의 절반만큼 부채. 100% = 자본 = 부채.\n"
            "200%+ 면 금리 인상시 이자부담 급증 위험. 단, 은행·금융업은 본질적으로 높음."
        ),
    ),
    GlossaryItem(
        key="매출 성장",
        title="매출 성장률 (Revenue YoY)",
        one_liner="전년 동기 대비 매출 성장. 20+ 고성장, 0- 정체/감소.",
        detail=(
            "Revenue Growth (Year-over-Year). 분기 매출을 1년 전 분기와 비교.\n"
            "이익 성장보다 신뢰성 높음 (이익은 회계적 조정 가능).\n"
            "꾸준한 매출 성장 = 사업 확장 중."
        ),
    ),
    GlossaryItem(
        key="EPS 성장",
        title="EPS 성장률 (Earnings YoY)",
        one_liner="전년 동기 대비 주당순이익 성장. 30+ 고성장.",
        detail=(
            "EPS = 순이익 ÷ 발행주식수. EPS Growth = 분기 EPS 전년 대비 변화율.\n"
            "주가의 가장 큰 동인. CANSLIM 등 성장주 전략의 핵심 지표.\n"
            "단, 일회성 이익이나 자사주 매입으로 부풀려질 수 있음."
        ),
    ),
    GlossaryItem(
        key="매출 분기 트렌드",
        title="매출 분기 트렌드",
        one_liner="최근 4분기 매출 추이. 3분기 연속 증가 = 가속 성장.",
        detail=(
            "QoQ 분기별 매출 흐름. 3분기 연속 증가 = 견고한 사업 모멘텀.\n"
            "3분기 연속 감소 = 구조적 위기 (반전 신호 확인 필요).\n"
            "혼조 패턴 = 시즌성 또는 일회성 변동."
        ),
    ),
    GlossaryItem(
        key="배당",
        title="배당수익률 (Dividend Yield)",
        one_liner="연간 배당금 ÷ 주가. 4%+ 고배당, 단 배당성향 100%↑면 지속성 의심.",
        detail=(
            "Dividend Yield = 연간 배당금 ÷ 주가 (%).\n"
            "고배당주는 안정적 현금흐름 매력. 단 배당성향(Payout Ratio = 배당/순이익) 100% 넘으면 \n"
            "이익보다 더 배당 = 지속 불가능. 한국 평균 약 2%, REITs/유럽 종목 4~6% 흔함."
        ),
    ),
    # ──── 현금흐름 분석 (Phase 1.5+) ────
    GlossaryItem(
        key="OCF 마진",
        title="OCF 마진 (영업현금 / 매출)",
        one_liner="매출의 몇 %가 실제 영업현금으로 들어오나. 12+ 양호, 25+ 우수.",
        detail=(
            "Operating Cash Flow Margin = 영업활동현금흐름 ÷ 매출.\n"
            "이익은 회계 조정 가능하지만 현금은 거짓 못함. \n"
            "영업이익률보다 더 정직한 사업 효율 지표.\n"
            "소프트웨어·플랫폼 30%+, 제조 8~15%, 유통 3~7% 정도."
        ),
    ),
    GlossaryItem(
        key="FCF 수익률",
        title="FCF 수익률 (Free Cash Flow Yield)",
        one_liner="잉여현금 ÷ 시가총액. 4+ 양호, 8+ 매우 매력적. 워런 버핏 핵심.",
        detail=(
            "FCF Yield = 잉여현금흐름(FCF) ÷ 시가총액.\n"
            "FCF = 영업현금 − 자본적 지출(CAPEX). 회사가 마음대로 쓸 수 있는 진짜 현금.\n"
            "주가의 역(逆)배수 — PER이 낮으면 좋듯 FCF Yield는 높을수록 매력.\n"
            "워런 버핏·하워드 막스 등 가치투자자 핵심 지표."
        ),
    ),
    GlossaryItem(
        key="OCF vs 순이익",
        title="OCF / 순이익 (이익의 질)",
        one_liner="영업현금 ÷ 순이익. 1.0+ 진짜 이익, 0.7- 회계 분식 의심.",
        detail=(
            "Operating Cash Flow / Net Income. 회계 이익이 실제 현금으로 얼마나 전환되는가.\n"
            "1.0+ = 이익보다 현금이 더 많이 들어옴 (감가상각 등 비현금 비용 효과 — 정상).\n"
            "0.7 미만 = 이익은 있는데 현금이 안 들어옴 → 매출채권·재고 부풀리기 의심.\n"
            "엔론 등 분식회계 사례에서 가장 먼저 무너진 지표."
        ),
    ),
    GlossaryItem(
        key="FCF 성장",
        title="FCF 성장률 (Free Cash Flow YoY)",
        one_liner="잉여현금 전년 대비 성장. 30+ 가속, -30 이하 위기.",
        detail=(
            "Free Cash Flow Growth (YoY). 전년 대비 잉여현금 변화율.\n"
            "EPS 성장보다 더 본질적 — 매출·이익이 같아도 CAPEX 늘면 FCF 감소.\n"
            "지속적인 FCF 성장 = 사업 수익성·자본 효율 모두 개선되는 중."
        ),
    ),
    # ──── 머니플로우 (Phase 1.5+) ────
    GlossaryItem(
        key="A/D Line",
        title="A/D Line (매집/분배)",
        one_liner="가격 위치 × 거래량 누적. 매집(↑) vs 분배(↓) 구분.",
        detail=(
            "Accumulation/Distribution Line. 종가가 일중 고저의 어느 위치인가에 거래량 가중.\n"
            "종가가 고가 근처면 매수 압력 누적, 저가 근처면 매도 압력 누적.\n"
            "OBV와 유사하나 일중 변동까지 반영해 더 민감."
        ),
    ),
    GlossaryItem(
        key="VWAP",
        title="VWAP (거래량 가중 평균가)",
        one_liner="20일 rolling 거래량 가중 평균가. 단기 매물대 추정.",
        detail=(
            "Volume Weighted Average Price = Σ(가격×거래량) / Σ거래량 (최근 20일).\n"
            "기관 트레이더의 단기 매수·매도 평균가. 종가가 VWAP 위면 매수자 우세, "
            "아래면 매도자 우세. ±3% 이내는 근접/혼조."
        ),
    ),
    GlossaryItem(
        key="외인+기관",
        title="외인·기관 순매수 (KR)",
        one_liner="기관·외국인의 5일 누적 순매수. 양수면 큰손 유입.",
        detail=(
            "한국거래소(KRX) 자료 — 외국인·기관 투자자의 일별 순매수 금액.\n"
            "큰손이 사면 추세 형성 가능성↑, 큰손이 팔면 단기 약세 가능.\n"
            "개인은 일반적으로 반대 매매 (역지표 성격)."
        ),
    ),
    GlossaryItem(
        key="매수일/매도일 거래량",
        title="매수일/매도일 거래량 비율",
        one_liner="상승일 vs 하락일 거래량. 1.5x↑ 매수세 우세.",
        detail=(
            "5일간 가격이 오른 날의 거래량 ÷ 떨어진 날의 거래량.\n"
            "1.5 이상 = 매수일에 거래 집중 (수급 우위), \n"
            "0.67 이하 = 매도일에 거래 집중 (수급 약세)."
        ),
    ),
    GlossaryItem(
        key="거래대금 추세",
        title="거래대금 추세",
        one_liner="5일 평균 거래대금 ÷ 20일 평균. 1.3x↑ 관심 증가.",
        detail=(
            "거래대금(가격×거래량)이 최근 5일 평균이 1달 평균보다 얼마나 큰가.\n"
            "관심 종목 진입의 선행 지표. 큰 자금 유입 직전에 거래대금 먼저 늘어남."
        ),
    ),
]


def find_relevant(check_names: set[str]) -> list[GlossaryItem]:
    """체크 이름들에 해당하는 지표 설명만 추려서 반환."""
    matched: list[GlossaryItem] = []
    seen = set()
    for cn in check_names:
        cn_lower = cn.lower()
        for item in GLOSSARY:
            if item.key in seen:
                continue
            if item.key.lower() in cn_lower or cn.startswith(item.title):
                matched.append(item)
                seen.add(item.key)
    return matched


def all_items() -> list[GlossaryItem]:
    return list(GLOSSARY)


__all__ = ["GlossaryItem", "GLOSSARY", "find_relevant", "all_items"]
