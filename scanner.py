"""Upbit 9AM Momentum Scanner.

Scans KRW markets using public Upbit APIs and ranks coins by momentum
around the Korea daily-session reset (09:00 KST).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

UPBIT_BASE_URL = "https://api.upbit.com/v1"
KST = timezone(timedelta(hours=9))


@dataclass(frozen=True)
class MomentumSignal:
    market: str
    trade_price: float
    change_rate: float
    day_range_position: float
    notional_24h_krw: float
    score: float


def _http_get_json(path: str, params: dict[str, object] | None = None) -> list[dict]:
    query = f"?{urlencode(params)}" if params else ""
    url = f"{UPBIT_BASE_URL}{path}{query}"
    req = Request(url, headers={"Accept": "application/json", "User-Agent": "upbit-9am-scanner"})
    try:
        with urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError) as exc:
        raise RuntimeError(f"Request failed for {url}: {exc}") from exc


def get_krw_markets() -> list[str]:
    markets = _http_get_json("/market/all", {"isDetails": "false"})
    return sorted(entry["market"] for entry in markets if entry["market"].startswith("KRW-"))


def batched(items: Iterable[str], n: int) -> Iterable[list[str]]:
    batch: list[str] = []
    for item in items:
        batch.append(item)
        if len(batch) == n:
            yield batch
            batch = []
    if batch:
        yield batch


def fetch_tickers(markets: list[str]) -> list[dict]:
    output: list[dict] = []
    for chunk in batched(markets, 100):
        output.extend(_http_get_json("/ticker", {"markets": ",".join(chunk)}))
        time.sleep(0.05)
    return output


def calculate_signal(ticker: dict, min_notional_krw: float) -> MomentumSignal | None:
    notional = float(ticker["acc_trade_price_24h"])
    if notional < min_notional_krw:
        return None

    opening = float(ticker["opening_price"])
    high = float(ticker["high_price"])
    low = float(ticker["low_price"])
    trade_price = float(ticker["trade_price"])
    change_rate = float(ticker["signed_change_rate"])

    intraday_range = max(high - low, 1e-9)
    day_range_position = max(0.0, min(1.0, (trade_price - low) / intraday_range))

    # Simple momentum blend: percent-change + location in the day range + liquidity boost.
    liquidity_term = min(1.0, notional / 50_000_000_000)
    score = (change_rate * 100 * 0.6) + (day_range_position * 30 * 0.3) + (liquidity_term * 10 * 0.1)

    return MomentumSignal(
        market=ticker["market"],
        trade_price=trade_price,
        change_rate=change_rate,
        day_range_position=day_range_position,
        notional_24h_krw=notional,
        score=score,
    )


def scan(top: int, min_notional_krw: float) -> list[MomentumSignal]:
    markets = get_krw_markets()
    tickers = fetch_tickers(markets)

    signals = [
        signal
        for ticker in tickers
        if (signal := calculate_signal(ticker, min_notional_krw)) is not None
    ]
    signals.sort(key=lambda s: s.score, reverse=True)
    return signals[:top]


def format_report(signals: list[MomentumSignal]) -> str:
    now_kst = datetime.now(tz=KST).strftime("%Y-%m-%d %H:%M:%S %Z")
    lines = [f"Upbit 9AM Momentum Scanner @ {now_kst}", "=" * 78]
    lines.append(f"{'Rank':<5} {'Market':<12} {'Change%':>8} {'RangePos':>8} {'24h Notional(KRW)':>20} {'Price':>14}")
    lines.append("-" * 78)
    for idx, s in enumerate(signals, start=1):
        lines.append(
            f"{idx:<5} {s.market:<12} {s.change_rate * 100:>7.2f}% {s.day_range_position:>8.2f}"
            f" {s.notional_24h_krw:>20,.0f} {s.trade_price:>14,.2f}"
        )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scan Upbit KRW markets for 9AM momentum leaders.")
    parser.add_argument("--top", type=int, default=15, help="Number of top signals to print.")
    parser.add_argument(
        "--min-notional-krw",
        type=float,
        default=5_000_000_000,
        help="Minimum 24h KRW traded value filter.",
    )
    parser.add_argument("--json", action="store_true", help="Output JSON instead of table.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.top <= 0:
        print("--top must be positive", file=sys.stderr)
        return 2
    if args.min_notional_krw < 0:
        print("--min-notional-krw must be non-negative", file=sys.stderr)
        return 2

    try:
        signals = scan(top=args.top, min_notional_krw=args.min_notional_krw)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps([s.__dict__ for s in signals], ensure_ascii=False, indent=2))
    else:
        print(format_report(signals))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
