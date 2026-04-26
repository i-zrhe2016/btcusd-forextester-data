#!/usr/bin/env python3
"""Download Binance BTCUSDT klines and convert them to ForexTester CSV."""

from __future__ import annotations

import argparse
import csv
import io
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import UTC, date, datetime, time as dt_time, timedelta
from pathlib import Path


BASE_URL = "https://data.binance.vision"
API_URL = "https://data-api.binance.vision/api/v3/klines"


def is_kline_data_row(row: list[str]) -> bool:
    return len(row) >= 6 and row[0].isdigit()


def timestamp_to_datetime(value: str) -> datetime:
    timestamp = int(value)
    divisor = 1_000_000 if timestamp >= 10_000_000_000_000 else 1_000
    return datetime.fromtimestamp(timestamp / divisor, tz=UTC)


def format_forextester_row(row: list[str], output_symbol: str) -> list[str]:
    opened_at = timestamp_to_datetime(row[0])
    return [
        output_symbol,
        opened_at.strftime("%Y.%m.%d"),
        opened_at.strftime("%H:%M"),
        row[1],
        row[2],
        row[3],
        row[4],
        row[5],
    ]


def month_start(day: date) -> date:
    return day.replace(day=1)


def next_month(day: date) -> date:
    if day.month == 12:
        return date(day.year + 1, 1, 1)
    return date(day.year, day.month + 1, 1)


def iter_months(start: date, end: date):
    cursor = month_start(start)
    while cursor <= end:
        yield cursor
        cursor = next_month(cursor)


def iter_days(start: date, end: date):
    cursor = start
    while cursor <= end:
        yield cursor
        cursor += timedelta(days=1)


def monthly_url(symbol: str, interval: str, month: date) -> str:
    month_id = month.strftime("%Y-%m")
    return (
        f"{BASE_URL}/data/spot/monthly/klines/{symbol}/{interval}/"
        f"{symbol}-{interval}-{month_id}.zip"
    )


def daily_url(symbol: str, interval: str, day: date) -> str:
    day_id = day.strftime("%Y-%m-%d")
    return (
        f"{BASE_URL}/data/spot/daily/klines/{symbol}/{interval}/"
        f"{symbol}-{interval}-{day_id}.zip"
    )


def request_bytes(url: str, retries: int = 3, sleep_seconds: float = 1.0) -> bytes:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise
            last_error = exc
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
        if attempt < retries:
            time.sleep(sleep_seconds * attempt)
    assert last_error is not None
    raise last_error


def iter_zip_csv_rows(zip_bytes: bytes):
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        csv_names = [name for name in archive.namelist() if name.endswith(".csv")]
        if len(csv_names) != 1:
            raise ValueError(f"Expected one CSV in archive, found {csv_names}")
        with archive.open(csv_names[0]) as csv_file:
            text_file = io.TextIOWrapper(csv_file, encoding="utf-8", newline="")
            yield from csv.reader(text_file)


def write_archive_rows(
    writer,
    url: str,
    output_symbol: str,
    start_at: datetime,
    end_before: datetime,
) -> int:
    zip_bytes = request_bytes(url)
    written = 0
    for row in iter_zip_csv_rows(zip_bytes):
        if not is_kline_data_row(row):
            continue
        opened_at = timestamp_to_datetime(row[0])
        if start_at <= opened_at < end_before:
            writer.writerow(format_forextester_row(row, output_symbol))
            written += 1
    return written


def fetch_api_klines(symbol: str, interval: str, start_at: datetime, end_before: datetime):
    start_ms = int(start_at.timestamp() * 1000)
    end_ms = int(end_before.timestamp() * 1000) - 1
    while start_ms <= end_ms:
        params = urllib.parse.urlencode(
            {
                "symbol": symbol,
                "interval": interval,
                "startTime": start_ms,
                "endTime": end_ms,
                "limit": 1000,
            }
        )
        data = request_json(f"{API_URL}?{params}")
        if not data:
            break
        for row in data:
            yield [str(value) for value in row]
        next_start = int(data[-1][6]) + 1
        if next_start <= start_ms:
            break
        start_ms = next_start


def request_json(url: str):
    import json

    return json.loads(request_bytes(url).decode("utf-8"))


def convert(
    *,
    source_symbol: str,
    output_symbol: str,
    interval: str,
    start_day: date,
    end_at: datetime,
    output_path: Path,
    include_header: bool,
    include_live: bool,
) -> dict[str, int | str]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    start_at = datetime.combine(start_day, dt_time.min, tzinfo=UTC)
    if end_at.tzinfo is None:
        end_at = end_at.replace(tzinfo=UTC)
    end_at = end_at.astimezone(UTC)

    rows_written = 0
    archives_downloaded = 0
    archives_missing = 0
    live_rows = 0
    live_error = ""

    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        if include_header:
            writer.writerow(["Symbol", "Date", "Time", "Open", "High", "Low", "Close", "Volume"])

        monthly_end = month_start(end_at.date()) - timedelta(days=1)
        for month in iter_months(start_day, monthly_end):
            url = monthly_url(source_symbol, interval, month)
            try:
                rows_written += write_archive_rows(writer, url, output_symbol, start_at, end_at)
                archives_downloaded += 1
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    archives_missing += 1
                    continue
                raise

        current_month = month_start(end_at.date())
        daily_start = max(start_day, current_month)
        daily_end = end_at.date() - timedelta(days=1)
        for day in iter_days(daily_start, daily_end):
            url = daily_url(source_symbol, interval, day)
            try:
                rows_written += write_archive_rows(writer, url, output_symbol, start_at, end_at)
                archives_downloaded += 1
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    archives_missing += 1
                    continue
                raise

        live_start = datetime.combine(end_at.date(), dt_time.min, tzinfo=UTC)
        if include_live and live_start < end_at:
            try:
                for row in fetch_api_klines(source_symbol, interval, live_start, end_at):
                    if not is_kline_data_row(row):
                        continue
                    writer.writerow(format_forextester_row(row, output_symbol))
                    rows_written += 1
                    live_rows += 1
            except Exception as exc:  # Keep archived history even if the live API is unavailable.
                live_error = str(exc)

    return {
        "output": str(output_path),
        "rows_written": rows_written,
        "archives_downloaded": archives_downloaded,
        "archives_missing": archives_missing,
        "live_rows": live_rows,
        "live_error": live_error,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download BTCUSDT 1m klines and convert to ForexTester-compatible CSV."
    )
    parser.add_argument("--source-symbol", default="BTCUSDT")
    parser.add_argument("--output-symbol", default="BTCUSD")
    parser.add_argument("--interval", default="1m")
    parser.add_argument("--start", default="2019-01-01", help="UTC start date, YYYY-MM-DD")
    parser.add_argument(
        "--end",
        default=None,
        help="UTC end datetime, exclusive. Defaults to current UTC time.",
    )
    parser.add_argument("--output", default="BTCUSD_1m_forextester_2019_to_now.csv")
    parser.add_argument("--header", action="store_true", help="Include a header row.")
    parser.add_argument(
        "--no-live",
        action="store_true",
        help="Do not fetch current-day candles from Binance API.",
    )
    return parser.parse_args(argv)


def parse_end(value: str | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if isinstance(parsed, datetime):
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    raise ValueError(f"Invalid end datetime: {value}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    stats = convert(
        source_symbol=args.source_symbol,
        output_symbol=args.output_symbol,
        interval=args.interval,
        start_day=date.fromisoformat(args.start),
        end_at=parse_end(args.end),
        output_path=Path(args.output),
        include_header=args.header,
        include_live=not args.no_live,
    )
    for key, value in stats.items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
