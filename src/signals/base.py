"""시그널 베이스 클래스 (공통 인터페이스)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass
class SignalResult:
    """시그널 1개의 결과 (사진 카드의 한 줄에 해당).

    예: 차트 시그널 ↑4 ↓3 △1
    """
    signal_type: str
    score_up: int = 0
    score_down: int = 0
    score_neut: int = 0
    summary: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def net(self) -> int:
        return self.score_up - self.score_down

    def to_emoji_line(self) -> str:
        """텔레그램용 1줄 출력. 예: '차트 시그널  ↑4 ↓3 △1'"""
        return f"{self.signal_type}  ↑{self.score_up} ↓{self.score_down} △{self.score_neut}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_type": self.signal_type,
            "score_up": self.score_up,
            "score_down": self.score_down,
            "score_neut": self.score_neut,
            "summary": self.summary,
            "details": self.details,
        }


class Signal(ABC):
    """시그널 분석기 베이스."""

    name: str = "base"

    @abstractmethod
    def analyze(self, df: pd.DataFrame, symbol: str, market: str) -> SignalResult: ...


__all__ = ["Signal", "SignalResult"]
