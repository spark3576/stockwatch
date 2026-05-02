"""StockWatch CLI 진입점.

Phase 1 명령어:
    python main.py init-db                  # DB 초기화
    python main.py test-telegram            # 텔레그램 봇 연결 확인
    python main.py analyze 005930           # 단일 종목 분석 (콘솔 출력)
    python main.py analyze AAPL --send      # 분석 + 텔레그램 발송
    python main.py analyze 7203.T --days 180
    python main.py info 005930              # 종목 메타 정보만
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# .env 우선 로드 (없으면 .env.example 폴백)
load_dotenv(ROOT / ".env")
if not (ROOT / ".env").exists():
    load_dotenv(ROOT / ".env.example")

from src.analyzer.composite import CompositeCard, build_card, detect_card_changes  # noqa: E402
from src.collectors.unified import collect_history, collect_info  # noqa: E402
from src.db.manager import DB  # noqa: E402
from src.notifier.telegram import TelegramNotifier, html_escape  # noqa: E402
from src.signals.base import SignalResult  # noqa: E402
from src.signals.breakout import BreakoutSignal  # noqa: E402
from src.signals.chart_pattern import ChartPattern  # noqa: E402
from src.signals.chart_signal import ChartSignal  # noqa: E402
from src.signals.ai_signals import FactHunter, GlobalMacro, WhyEngine  # noqa: E402
from src.signals.event_tracker import EventTracker  # noqa: E402
from src.signals.financial_signal import FinancialSignal  # noqa: E402
from src.signals.glossary import all_items as glossary_all, find_relevant  # noqa: E402
from src.signals.money_flow import MoneyFlowSignal  # noqa: E402
from src.signals.quant_factor import QuantFactor  # noqa: E402
from src.utils.logger import logger, setup_logger  # noqa: E402
from src.utils.markets import market_info  # noqa: E402

console = Console()


@click.group(help="StockWatch — 다국가 주식 분석 + 텔레그램 자동 리포트.")
@click.option("--log-level", default=None, help="DEBUG/INFO/WARNING/ERROR")
def cli(log_level: str | None) -> None:
    setup_logger(log_level)


@cli.command("init-db", help="SQLite DB 초기화 (스키마 생성).")
def cmd_init_db() -> None:
    db = DB()
    db.init_schema()
    console.print(f"[green]✅ DB 초기화 완료:[/green] {db.db_path}")


@cli.command("test-telegram", help="텔레그램 봇 연결 테스트 + 헬로 메시지 발송.")
def cmd_test_tg() -> None:
    tg = TelegramNotifier()
    if not tg.test():
        console.print("[red]❌ 텔레그램 봇 연결 실패. .env의 토큰 확인[/red]")
        sys.exit(1)
    text = (
        "<b>📊 StockWatch 봇 연결 성공</b>\n\n"
        f"시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        "Phase 1 — 차트 시그널 모듈 준비 완료 ✅\n\n"
        "<i>이제 종목 분석 결과를 여기로 받을 수 있습니다.</i>"
    )
    tg.send_text(text)
    console.print("[green]✅ 헬로 메시지 발송 완료. 텔레그램 확인하세요![/green]")


@cli.command("glossary", help="기술적 지표 사전 (모든 지표 한줄 요약 + 상세 설명).")
@click.option("--detail", is_flag=True, help="각 지표 상세 설명까지")
@click.option("--key", default=None, help="특정 지표만 (예: --key RSI)")
def cmd_glossary(detail: bool, key: str | None) -> None:
    items = glossary_all()
    if key:
        items = [i for i in items if key.lower() in i.title.lower() or key.lower() in i.key.lower()]
        if not items:
            console.print(f"[red]'{key}' 매칭 항목 없음[/red]")
            return
    for item in items:
        console.print(f"[bold cyan]{item.title}[/bold cyan]  ([dim]{item.key}[/dim])")
        console.print(f"  → {item.one_liner}")
        if detail:
            console.print(f"  [dim]{item.detail}[/dim]")
        console.print()


@cli.command("cards", help="저장된 분석 카드 이력 조회.")
@click.option("--symbol", default=None, help="특정 종목만 (예: --symbol AAPL)")
@click.option("--limit", default=10, help="조회 개수 (기본 10)")
def cmd_cards(symbol: str | None, limit: int) -> None:
    db = DB()
    cards = db.list_cards(symbol=symbol, limit=limit)
    if not cards:
        console.print("[yellow]저장된 카드 없음[/yellow]")
        return
    table = Table(show_header=True, header_style="bold magenta",
                  title=f"📇 분석 카드 이력 ({len(cards)}건)")
    table.add_column("ID", justify="right", style="dim")
    table.add_column("발행일", style="cyan")
    table.add_column("종목", style="cyan")
    table.add_column("시장")
    table.add_column("발행가", justify="right")
    table.add_column("판정")
    table.add_column("리스크")
    for row in cards:
        triggers = json.loads(row.get("triggers_json") or "{}")
        signals_d = json.loads(row.get("signals_json") or "{}")
        verdict = triggers.get("verdict", "?")
        risk_level = triggers.get("risk_level", "?")
        risk_score = triggers.get("risk_score", "-")
        scores = signals_d.get("scores", {})
        verdict_str = (
            f"{verdict}  ↑{scores.get('up','-')} ↓{scores.get('down','-')} △{scores.get('neut','-')}"
        )
        risk_str = f"{risk_level} ({risk_score})"
        issued = (row.get("issued_at") or "").split(".")[0].replace("T", " ")
        price = row.get("issue_price")
        price_s = f"{price:,.2f}" if isinstance(price, (int, float)) else "-"
        table.add_row(
            str(row.get("id")), issued, row.get("symbol"),
            row.get("market"), price_s, verdict_str, risk_str,
        )
    console.print(table)


@cli.group("watch", help="워치리스트 관리 (Phase 2).")
def cmd_watch_group() -> None:
    pass


@cmd_watch_group.command("add", help="워치리스트에 종목 추가. 예: watch add 005930 --alias '장기보유'")
@click.argument("symbol")
@click.option("--alias", default=None, help="종목 별명 (선택)")
def cmd_watch_add(symbol: str, alias: str | None) -> None:
    from src.utils.markets import detect_market, normalize_symbol
    market = detect_market(symbol)
    nsym = normalize_symbol(symbol)
    db = DB()
    db.add_watchlist(nsym, market, alias)
    info = collect_info(symbol)
    if info.get("name"):
        db.upsert_security(
            symbol=nsym, market=market, name=info["name"],
            sector=info.get("sector"), industry=info.get("industry"),
            currency=info.get("currency"),
        )
    flag = {"KR": "🇰🇷", "US": "🇺🇸", "JP": "🇯🇵", "UK": "🇬🇧", "DE": "🇩🇪"}.get(market, "")
    console.print(f"[green]✅ 추가:[/green] {flag} {info.get('name') or nsym} ({nsym}, {market})"
                  + (f" [dim]@{alias}[/dim]" if alias else ""))


@cmd_watch_group.command("remove", help="워치리스트에서 종목 제거.")
@click.argument("symbol")
def cmd_watch_remove(symbol: str) -> None:
    from src.utils.markets import normalize_symbol
    nsym = normalize_symbol(symbol)
    db = DB()
    n = db.remove_watchlist(nsym)
    if n:
        console.print(f"[green]✅ 제거:[/green] {nsym} ({n}건)")
    else:
        console.print(f"[yellow]해당 종목 없음:[/yellow] {nsym}")


@cmd_watch_group.command("list", help="워치리스트 조회.")
def cmd_watch_list() -> None:
    db = DB()
    items = db.list_watchlist()
    if not items:
        console.print("[yellow]워치리스트 비어있음. `watch add` 로 추가하세요.[/yellow]")
        return
    table = Table(title=f"📋 워치리스트 ({len(items)}종목)", header_style="bold magenta")
    table.add_column("종목", style="cyan")
    table.add_column("시장")
    table.add_column("별명", style="dim")
    table.add_column("등록일", style="dim")
    table.add_column("최종 분석일", style="dim")
    flag = {"KR": "🇰🇷", "US": "🇺🇸", "JP": "🇯🇵", "UK": "🇬🇧", "DE": "🇩🇪"}
    for it in items:
        added = (it.get("added_at") or "").split(".")[0].replace("T", " ")
        last = (it.get("last_analyzed_at") or "-").split(".")[0].replace("T", " ")
        flg = flag.get(it["market"], "")
        table.add_row(
            f"{flg} {it['symbol']}", it["market"],
            it.get("alias") or "-", added, last,
        )
    console.print(table)


@cli.command("report-daily", help="워치리스트 전 종목 분석 → 종합 데일리 리포트 (텔레그램 발송).")
@click.option("--send", is_flag=True, help="텔레그램으로 발송")
@click.option("--days", default=400, help="조회 기간 (기본 400)")
def cmd_report_daily(send: bool, days: int) -> None:
    db = DB()
    items = db.list_watchlist()
    if not items:
        console.print("[yellow]워치리스트 비어있음. `watch add SYMBOL` 으로 추가하세요.[/yellow]")
        return

    console.print(f"[bold]🌅 데일리 리포트 — {len(items)}종목 분석 시작[/bold]\n")
    cards: list[tuple[CompositeCard, list[SignalResult], object]] = []  # (card, results, df)
    failures: list[str] = []
    for it in items:
        sym = it["symbol"]
        market = it["market"]
        # 시장 접미사 추가 (KR은 그대로, 다른 건 이미 .T/.L/.DE 형태)
        symbol_input = sym  # collect_history가 자동 detect_market 사용
        try:
            out = run_analysis(symbol_input, days=days, save=True, db=db)
            if out is None:
                failures.append(f"{sym}({market})")
                continue
            card, results, df, _mi, _name, _mkt, nsym = out
            cards.append((card, results, df))
            db.update_watchlist_analyzed(nsym, market)
            console.print(f"  ✓ {card.overall_emoji}  {card.name}  ({sym}, {market})  ↑{card.total_up} ↓{card.total_down}")
        except Exception as e:
            logger.error(f"{sym} 분석 실패: {e}")
            failures.append(f"{sym}({market})")

    if not cards:
        console.print("[red]분석 가능한 종목 없음[/red]")
        return

    # 종합 리포트 생성
    msg = _format_daily_report([c[0] for c in cards], failures)
    console.print()
    console.print(Panel(msg.replace("<b>", "").replace("</b>", "")
                              .replace("<i>", "").replace("</i>", "")
                              .replace("<code>", "").replace("</code>", ""),
                          title="📨 데일리 리포트 (콘솔 미리보기)",
                          border_style="blue"))

    if send:
        tg = TelegramNotifier()
        tg.send_text(msg)
        db.log_notification("telegram", tg.chat_id, "daily",
                          {"count": len(cards), "failures": failures})
        console.print("[green]✅ 텔레그램 발송 완료[/green]")


def _format_daily_report(cards: list[CompositeCard], failures: list[str]) -> str:
    """N종목 종합 데일리 리포트 (4096자 안에 들어가게 압축)."""
    today = datetime.now().strftime("%Y-%m-%d (%a)")
    flag_map = {"KR": "🇰🇷", "US": "🇺🇸", "JP": "🇯🇵", "UK": "🇬🇧", "DE": "🇩🇪"}

    # 그룹화
    groups: dict[str, list[CompositeCard]] = {
        "🟢🟢 강한 상승": [],
        "🟢 상승 우위 / 약한 상승": [],
        "🟡 혼조": [],
        "🔴 약한 하락 / 하락 우위": [],
        "🔴🔴 강한 하락": [],
    }
    for c in cards:
        v = c.overall_verdict
        if "강한 상승" in v:
            groups["🟢🟢 강한 상승"].append(c)
        elif "상승" in v:
            groups["🟢 상승 우위 / 약한 상승"].append(c)
        elif "강한 하락" in v:
            groups["🔴🔴 강한 하락"].append(c)
        elif "하락" in v:
            groups["🔴 약한 하락 / 하락 우위"].append(c)
        else:
            groups["🟡 혼조"].append(c)

    lines = [
        f"<b>🌅 데일리 리포트 — {today}</b>",
        f"<i>워치리스트 {len(cards)}종목 분석</i>",
        "",
    ]

    for group_name, group_cards in groups.items():
        if not group_cards:
            continue
        lines.append(f"<b>{group_name}</b> ({len(group_cards)})")
        for c in group_cards:
            flag = flag_map.get(c.market, "")
            name_e = html_escape(c.name)
            sym_e = html_escape(c.symbol)
            risk_emoji = {"낮음": "🟢", "보통": "🟡", "높음": "🟠", "매우 높음": "🔴"}.get(c.risk_level, "⚪")
            lines.append(
                f"• {flag} <b>{name_e}</b> <code>{sym_e}</code>  "
                f"{c.issue_price:,.2f} {c.currency}"
            )
            lines.append(
                f"   ↑{c.total_up} ↓{c.total_down} {risk_emoji}리스크 {c.risk_score}  "
                f"<i>{html_escape(c.summary_oneliner.replace('🟢🟢','').replace('🟢','').replace('🔴🔴','').replace('🔴','').replace('🟡','').replace('⚠️','').strip())}</i>"
            )
        lines.append("")

    # 통계
    total_up = sum(c.total_up for c in cards)
    total_dn = sum(c.total_down for c in cards)
    lines.append(f"<b>━━━ 종합 ━━━</b>")
    lines.append(f"전체 ↑{total_up} ↓{total_dn} 종목 {len(cards)}개")
    n_strong_up = len(groups["🟢🟢 강한 상승"])
    n_up = len(groups["🟢 상승 우위 / 약한 상승"])
    n_dn = len(groups["🔴 약한 하락 / 하락 우위"]) + len(groups["🔴🔴 강한 하락"])
    n_mixed = len(groups["🟡 혼조"])
    lines.append(f"강세 {n_strong_up + n_up} · 혼조 {n_mixed} · 약세 {n_dn}")
    if failures:
        lines.append(f"<i>분석 실패: {', '.join(failures)}</i>")

    return "\n".join(lines)


@cli.command("report-changes", help="워치리스트 분석 → 직전 카드와 비교, 변화 있는 종목만 알림.")
@click.option("--send", is_flag=True, help="텔레그램 발송")
@click.option("--days", default=400, help="조회 기간")
@click.option("--quiet", is_flag=True, help="콘솔 출력 최소화")
def cmd_report_changes(send: bool, days: int, quiet: bool) -> None:
    db = DB()
    items = db.list_watchlist()
    if not items:
        console.print("[yellow]워치리스트 비어있음[/yellow]")
        return

    if not quiet:
        console.print(f"[bold]🔍 변화 감지 — {len(items)}종목 분석[/bold]\n")

    changed_items: list[tuple[CompositeCard, list[dict]]] = []
    for it in items:
        sym = it["symbol"]
        market = it["market"]
        # 비교 기준: 분석 전 가장 최근 카드 (limit=1)
        prior_cards = db.list_cards(symbol=sym, limit=1)
        prior = None
        if prior_cards:
            try:
                prior = json.loads(prior_cards[0].get("signals_json") or "{}")
                # triggers_json에서 verdict/risk_level 확보
                trig = json.loads(prior_cards[0].get("triggers_json") or "{}")
                prior["verdict"] = trig.get("verdict")
                prior["risk_level"] = trig.get("risk_level")
            except Exception:
                prior = None

        try:
            out = run_analysis(sym, days=days, save=True, db=db)
        except Exception as e:
            logger.error(f"{sym} 실패: {e}")
            continue
        if out is None:
            continue
        card, results, df, _mi, _name, _mkt, nsym = out
        db.update_watchlist_analyzed(nsym, market)

        if not prior:
            if not quiet:
                console.print(f"  • {card.name} ({sym}): 비교 기준 없음 (첫 분석)")
            continue

        changes = detect_card_changes(prior, card)
        if changes:
            changed_items.append((card, changes))
            if not quiet:
                console.print(f"  ⚡ {card.overall_emoji} {card.name} ({sym}): {len(changes)}개 변화")
        else:
            if not quiet:
                console.print(f"  ○ {card.name} ({sym}): 변화 없음")

    if not changed_items:
        if not quiet:
            console.print("\n[dim]전 종목 변화 없음 — 알림 발송 안 함[/dim]")
        return

    msg = _format_changes_alert(changed_items)
    if not quiet:
        console.print()
        console.print(Panel(
            msg.replace("<b>", "").replace("</b>", "")
               .replace("<i>", "").replace("</i>", "")
               .replace("<code>", "").replace("</code>", ""),
            title="⚡ 변화 알림 (콘솔 미리보기)", border_style="yellow",
        ))

    if send:
        tg = TelegramNotifier()
        tg.send_text(msg)
        db.log_notification("telegram", tg.chat_id, "signal",
                          {"changed": len(changed_items)})
        console.print("[green]✅ 텔레그램 발송 완료[/green]")


def _format_changes_alert(items: list[tuple[CompositeCard, list[dict]]]) -> str:
    """변화 알림 메시지 포맷."""
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    flag_map = {"KR": "🇰🇷", "US": "🇺🇸", "JP": "🇯🇵", "UK": "🇬🇧", "DE": "🇩🇪"}

    lines = [
        f"<b>⚡ 시그널 변화 알림 — {today}</b>",
        f"<i>{len(items)}개 종목에 의미있는 변화 감지</i>",
        "",
    ]

    for card, changes in items:
        flag = flag_map.get(card.market, "")
        name_e = html_escape(card.name)
        sym_e = html_escape(card.symbol)
        lines.append(f"<b>{flag} {name_e}</b> <code>{sym_e}</code>  {card.issue_price:,.2f} {card.currency}")
        lines.append(f"  현재: {card.overall_emoji} {html_escape(card.overall_verdict)}  ↑{card.total_up} ↓{card.total_down}")

        # 변화 내역
        for ch in changes:
            if ch["type"] == "verdict":
                emoji = "🔄" if ch["severity"] == "major" else "↔️"
                lines.append(f"  {emoji} 판정: {html_escape(ch['from'])} → <b>{html_escape(ch['to'])}</b>")
            elif ch["type"] == "risk":
                emoji = "🔺" if ch["direction"] == "up" else "🔻"
                lines.append(f"  {emoji} 리스크: {html_escape(ch['from'])} → {html_escape(ch['to'])}")
            elif ch["type"] == "signal":
                arrow = "📈" if ch["delta"] > 0 else "📉"
                sig_name = html_escape(ch["signal_name"])
                lines.append(f"  {arrow} {sig_name}: {ch['prev']} → {ch['curr']} ({ch['delta']:+d})")
            elif ch["type"] == "price":
                arrow = "🚀" if ch["pct"] > 0 else "💥"
                lines.append(f"  {arrow} 가격: {ch['prev']:,.2f} → {ch['curr']:,.2f} ({ch['pct']:+.1f}%)")

        # 한줄 요약
        lines.append(f"  💡 <i>{html_escape(card.summary_oneliner)}</i>")
        lines.append("")

    return "\n".join(lines)


@cli.command("info", help="종목 메타 정보 조회.")
@click.argument("symbol")
def cmd_info(symbol: str) -> None:
    info = collect_info(symbol)
    table = Table(title=f"📋 {info.get('name') or symbol}")
    table.add_column("항목", style="cyan")
    table.add_column("값")
    for k, v in info.items():
        table.add_row(str(k), str(v) if v is not None else "-")
    console.print(table)


def run_analysis(symbol: str, days: int = 400, save: bool = True, db: DB | None = None):
    """단일 종목 분석 헬퍼 — cmd_analyze + report_daily에서 공유.

    반환: (card, results, df, mi, name, market, nsym) 또는 None (데이터 없음).
    """
    db = db or DB()
    info = collect_info(symbol)
    df, market = collect_history(symbol, days=days)
    if df.empty:
        return None

    nsym = info["symbol"]
    name = info.get("name") or nsym
    mi = market_info(market)

    if save:
        db.upsert_security(
            symbol=nsym, market=market, name=name,
            sector=info.get("sector"), industry=info.get("industry"),
            currency=info.get("currency"),
        )
        db.insert_prices(nsym, market, df)

    # Phase 3: 6 기본 + 1 이벤트 + 3 AI = 10개 시그널 (사진의 8 + 퀀트·재무 추가)
    signals = [
        ChartSignal(), ChartPattern(), BreakoutSignal(),
        MoneyFlowSignal(), QuantFactor(), FinancialSignal(),
        EventTracker(),
        FactHunter(), WhyEngine(), GlobalMacro(),
    ]
    results: list[SignalResult] = []
    for sig in signals:
        try:
            r = sig.analyze(df, nsym, market)
            results.append(r)
            if save:
                db.insert_signal(
                    symbol=nsym, market=market, signal_type=sig.name,
                    score_up=r.score_up, score_down=r.score_down, score_neut=r.score_neut,
                    payload=r.details,
                )
        except Exception as e:
            logger.error(f"{sig.name} 실패: {e}")

    card = build_card(
        symbol=nsym, market=market, name=name,
        issue_price=float(df["close"].iloc[-1]),
        currency=mi.currency,
        signals=results,
    )
    if save:
        db.save_composite_card(card.to_dict())

    return card, results, df, mi, name, market, nsym


@cli.command("analyze", help="종목 분석 (6개 시그널). 옵션: --send 로 텔레그램 발송.")
@click.argument("symbol")
@click.option("--days", default=400, help="조회 기간 (일, 200일선 위해 최소 400 권장)")
@click.option("--send", is_flag=True, help="결과를 텔레그램으로 발송")
@click.option("--save", is_flag=True, default=True, help="DB에 저장 (기본 ON)")
@click.option("--detail", is_flag=True, help="모든 체크 항목 상세 출력")
def cmd_analyze(symbol: str, days: int, send: bool, save: bool, detail: bool) -> None:
    db = DB()
    out = run_analysis(symbol, days=days, save=save, db=db)
    if out is None:
        console.print(f"[red]❌ {symbol} 데이터 없음[/red]")
        sys.exit(1)
    card, results, df, mi, name, market, nsym = out

    _print_composite(card, df)
    _print_results(name, nsym, market, mi.currency, df, results, detail=detail)

    if send:
        tg = TelegramNotifier()
        msg = _format_telegram_card(card, results, df)
        tg.send_text(msg)
        db.log_notification("telegram", tg.chat_id, "manual", {"symbol": nsym, "market": market})
        console.print("[green]✅ 텔레그램 발송 완료[/green]")


def _print_composite(card: CompositeCard, df) -> None:
    """통합 종합 카드를 콘솔에 큰 박스로 출력 (사진 카드 스타일)."""
    flag = {"KR": "🇰🇷", "US": "🇺🇸", "JP": "🇯🇵", "UK": "🇬🇧", "DE": "🇩🇪"}.get(card.market, "")
    last_date = df.index[-1].strftime("%Y-%m-%d")

    risk_color = {"낮음": "green", "보통": "yellow", "높음": "red", "매우 높음": "red bold"}.get(card.risk_level, "white")

    body = (
        f"{flag} [bold]{card.name}[/bold]  ([cyan]{card.symbol}[/cyan], {card.market})\n"
        f"📅 {last_date}  ·  💵 [yellow]{card.issue_price:,.2f} {card.currency}[/yellow]\n\n"
        f"📊 [bold]{card.overall_emoji}  {card.overall_verdict}[/bold]   "
        f"(↑{card.total_up} ↓{card.total_down} △{card.total_neut})\n"
        f"⚠️  리스크: [{risk_color}]{card.risk_level} ({card.risk_score}/100)[/{risk_color}]\n\n"
        f"[bold italic]{card.summary_oneliner}[/bold italic]"
    )
    console.print(Panel(body, border_style="blue", title="🔬 통합 분석 카드", expand=False))

    # 강점/약점
    if card.strengths or card.weaknesses:
        st_table = Table(show_header=True, header_style="bold magenta", title="✨ 핵심 강점 / ⚠️ 주의 신호")
        st_table.add_column("시그널", style="cyan", width=12)
        st_table.add_column("체크", width=20)
        st_table.add_column("판정", justify="center")
        st_table.add_column("근거")
        for s in card.strengths[:5]:
            st_table.add_row(s["signal"], s["name"], "[green]↑[/green]", s["reason"])
        for w in card.weaknesses[:5]:
            st_table.add_row(w["signal"], w["name"], "[red]↓[/red]", w["reason"])
        console.print(st_table)

    # 리스크 요인
    if card.risk_factors:
        rf_lines = "\n".join(f"  • {f}" for f in card.risk_factors)
        console.print(Panel(rf_lines, border_style=risk_color, title="⚠️ 리스크 요인"))


def _print_results(
    name: str, symbol: str, market: str, currency: str, df,
    results: list[SignalResult], detail: bool = False,
) -> None:
    # 시그널 요약 카드 (사진 스타일) — 통합 카드 다음에 출력
    summary_table = Table(show_header=True, header_style="bold magenta", title="📊 10개 시그널 요약")
    summary_table.add_column("시그널", style="cyan", no_wrap=True)
    summary_table.add_column("↑", justify="center", style="green")
    summary_table.add_column("↓", justify="center", style="red")
    summary_table.add_column("△", justify="center", style="yellow")
    summary_table.add_column("종합 판정", style="white")
    for r in results:
        summary_table.add_row(
            r.signal_type,
            str(r.score_up), str(r.score_down), str(r.score_neut),
            r.summary,
        )
    console.print(summary_table)

    if detail:
        for r in results:
            t = Table(show_header=True, header_style="bold cyan",
                      title=f"  ↳ {r.signal_type} 상세")
            t.add_column("체크", style="cyan", no_wrap=True)
            t.add_column("결과", justify="center")
            t.add_column("근거")
            for chk in r.details.get("checks", []):
                color = {"↑": "green", "↓": "red", "△": "yellow"}.get(chk["verdict"], "white")
                t.add_row(chk["name"], f"[{color}]{chk['verdict']}[/{color}]", chk["reason"])
            console.print(t)


def _format_telegram_card(
    card: CompositeCard, results: list[SignalResult], df,
) -> str:
    """통합 카드 + 10개 시그널 요약 + 강점/약점 + 디테일 + 지표해설."""
    flag = {"KR": "🇰🇷", "US": "🇺🇸", "JP": "🇯🇵", "UK": "🇬🇧", "DE": "🇩🇪"}.get(card.market, "")
    last_date = df.index[-1].strftime("%Y-%m-%d")
    name_e = html_escape(card.name)
    sym_e = html_escape(card.symbol)

    risk_emoji = {"낮음": "🟢", "보통": "🟡", "높음": "🟠", "매우 높음": "🔴"}.get(card.risk_level, "⚪")

    lines = [
        f"<b>━━━━━ 🔬 통합 분석 카드 ━━━━━</b>",
        f"<b>{flag} {name_e}</b>  <code>{sym_e}</code> · {card.market}",
        f"📅 {last_date}  ·  💵 <b>{card.issue_price:,.2f} {card.currency}</b>",
        "",
        f"📊 <b>{card.overall_emoji}  {html_escape(card.overall_verdict)}</b>  ↑{card.total_up} ↓{card.total_down} △{card.total_neut}",
        f"⚠️  리스크: {risk_emoji} <b>{card.risk_level}</b> ({card.risk_score}/100)",
        "",
        f"<b>💡 {html_escape(card.summary_oneliner)}</b>",
        "",
    ]

    # 강점
    if card.strengths:
        lines.append("<b>━━ ✨ 핵심 강점 ━━</b>")
        for s in card.strengths[:5]:
            lines.append(f"  ↑ <i>[{html_escape(s['signal'])}]</i> {html_escape(s['name'])} — {html_escape(s['reason'])}")
        lines.append("")

    # 약점
    if card.weaknesses:
        lines.append("<b>━━ ⚠️ 주의 신호 ━━</b>")
        for w in card.weaknesses[:5]:
            lines.append(f"  ↓ <i>[{html_escape(w['signal'])}]</i> {html_escape(w['name'])} — {html_escape(w['reason'])}")
        lines.append("")

    # 리스크 요인
    if card.risk_factors:
        lines.append("<b>━━ ⚠️ 리스크 요인 ━━</b>")
        for f in card.risk_factors:
            lines.append(f"  • {html_escape(f)}")
        lines.append("")

    # 10개 시그널 요약
    lines.append("<b>━━ 📊 10개 시그널 요약 ━━</b>")
    for r in results:
        sig_e = html_escape(r.signal_type)
        lines.append(f"<code>{sig_e:<11}</code> ↑{r.score_up} ↓{r.score_down} △{r.score_neut}  <i>{html_escape(r.summary)}</i>")
    lines.append("")

    # 시그널 상세
    lines.append("<b>━━ 📋 상세 체크 ━━</b>")
    all_check_names: set[str] = set()
    for r in results:
        lines.append(f"\n<u>{html_escape(r.signal_type)}</u>")
        for chk in r.details.get("checks", []):
            verdict = chk["verdict"]
            chk_name = html_escape(chk["name"])
            reason = html_escape(chk["reason"])
            lines.append(f"  {verdict} {chk_name} — {reason}")
            all_check_names.add(chk["name"])

    # 지표 해설
    relevant = find_relevant(all_check_names)
    if relevant:
        lines.append("")
        lines.append("<b>━━ 📚 지표 해설 ━━</b>")
        for item in relevant:
            t = html_escape(item.title)
            o = html_escape(item.one_liner)
            lines.append(f"• <b>{t}</b>: {o}")

    return "\n".join(lines)


def _format_telegram_multi(
    name: str, symbol: str, market: str, currency: str, df, results: list[SignalResult],
) -> str:
    last_close = df["close"].iloc[-1]
    last_date = df.index[-1].strftime("%Y-%m-%d")
    flag = {"KR": "🇰🇷", "US": "🇺🇸", "JP": "🇯🇵", "UK": "🇬🇧", "DE": "🇩🇪"}.get(market, "")

    name_e = html_escape(name)
    sym_e = html_escape(symbol)

    # 종합 점수 (3개 시그널 합산)
    total_up = sum(r.score_up for r in results)
    total_down = sum(r.score_down for r in results)
    total_neut = sum(r.score_neut for r in results)
    net = total_up - total_down
    if net >= 8:
        overall = "🟢 강한 상승"
    elif net >= 3:
        overall = "🟢 상승 우위"
    elif net <= -8:
        overall = "🔴 강한 하락"
    elif net <= -3:
        overall = "🔴 하락 우위"
    else:
        overall = "🟡 혼조"

    lines = [
        f"<b>{flag} {name_e}</b>  <code>{sym_e}</code>",
        f"📅 {last_date}  ·  💵 <b>{last_close:,.2f} {currency}</b>",
        f"📈 종합: <b>{overall}</b>  (총 ↑{total_up} ↓{total_down} △{total_neut})",
        "",
        "<b>━━━━━ 시그널 요약 ━━━━━</b>",
    ]
    for r in results:
        sig_e = html_escape(r.signal_type)
        lines.append(f"<code>{sig_e:<11}</code> ↑{r.score_up} ↓{r.score_down} △{r.score_neut}  <i>{html_escape(r.summary)}</i>")
    lines.append("")

    # 각 시그널 상세
    lines.append("<b>━━━━━ 상세 체크 ━━━━━</b>")
    all_check_names: set[str] = set()
    for r in results:
        lines.append(f"\n<u>{html_escape(r.signal_type)}</u>")
        for chk in r.details.get("checks", []):
            verdict = chk["verdict"]
            chk_name = html_escape(chk["name"])
            reason = html_escape(chk["reason"])
            lines.append(f"  {verdict} {chk_name} — {reason}")
            all_check_names.add(chk["name"])

    # 지표 한줄 해설 (이 메시지에 등장한 지표만 추려서)
    relevant = find_relevant(all_check_names)
    if relevant:
        lines.append("")
        lines.append("<b>━━━━━ 지표 해설 ━━━━━</b>")
        for item in relevant:
            t = html_escape(item.title)
            o = html_escape(item.one_liner)
            lines.append(f"• <b>{t}</b>: {o}")
        lines.append("")
        lines.append("<i>더 자세히: <code>python main.py glossary --detail</code></i>")

    return "\n".join(lines)


if __name__ == "__main__":
    cli()
