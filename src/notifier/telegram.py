"""텔레그램 봇 알림 (Phase 1: 동기 HTTP API 직접 호출).

python-telegram-bot 라이브러리 대신 단순 requests로 시작 → 의존성 최소화.
"""
from __future__ import annotations

import html
import os
from typing import Any

import requests

from src.utils.logger import logger

API_BASE = "https://api.telegram.org/bot{token}/{method}"


def html_escape(text: str) -> str:
    """텔레그램 HTML 모드용 escape (< > & 만 처리)."""
    return html.escape(str(text), quote=False)


class TelegramNotifier:
    def __init__(self, token: str | None = None, chat_id: str | None = None) -> None:
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
        if not self.token or not self.chat_id:
            raise RuntimeError(
                "TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 환경변수 필요 (.env 파일 확인)"
            )

    MAX_LEN = 4000  # 텔레그램 한 메시지 4096자 제한 — 마진 96자

    def send_text(self, text: str, parse_mode: str = "HTML") -> dict[str, Any]:
        """단일 메시지 발송. 4000자 초과시 자동 분할."""
        if len(text) <= self.MAX_LEN:
            return self._send_one(text, parse_mode)

        # 4000자 초과 → 안전한 지점에서 분할 (줄바꿈 우선)
        chunks = self._split_safely(text, self.MAX_LEN)
        last_resp: dict[str, Any] = {}
        for i, chunk in enumerate(chunks):
            header = f"<i>[{i+1}/{len(chunks)}]</i>\n" if len(chunks) > 1 else ""
            last_resp = self._send_one(header + chunk, parse_mode)
        return last_resp

    def _send_one(self, text: str, parse_mode: str = "HTML") -> dict[str, Any]:
        url = API_BASE.format(token=self.token, method="sendMessage")
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }
        try:
            resp = requests.post(url, json=payload, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if not data.get("ok"):
                logger.error(f"텔레그램 응답 오류: {data}")
            return data
        except requests.RequestException as e:
            logger.error(f"텔레그램 전송 실패 ({len(text)}자): {e}")
            raise

    @staticmethod
    def _split_safely(text: str, max_len: int) -> list[str]:
        """줄바꿈 → 공백 우선순위로 분할."""
        if len(text) <= max_len:
            return [text]
        chunks: list[str] = []
        remaining = text
        while len(remaining) > max_len:
            # 줄바꿈 위치 찾기 (뒤에서)
            split_at = remaining.rfind("\n", 0, max_len)
            if split_at < max_len // 2:
                # 줄바꿈이 너무 앞이면 공백으로
                split_at = remaining.rfind(" ", 0, max_len)
            if split_at < 0:
                split_at = max_len
            chunks.append(remaining[:split_at])
            remaining = remaining[split_at:].lstrip()
        if remaining:
            chunks.append(remaining)
        return chunks

    def test(self) -> bool:
        """봇 정상 작동 확인."""
        url = API_BASE.format(token=self.token, method="getMe")
        try:
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            data = r.json()
            ok = bool(data.get("ok"))
            if ok:
                bot = data["result"]
                logger.info(f"✅ 텔레그램 봇 연결 성공: @{bot.get('username')} ({bot.get('first_name')})")
            return ok
        except Exception as e:
            logger.error(f"텔레그램 연결 실패: {e}")
            return False


__all__ = ["TelegramNotifier"]
