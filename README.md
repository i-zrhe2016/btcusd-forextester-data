# BTCUSD ForexTester Data

BTCUSD 1-minute historical data formatted for ForexTester import.

The dataset is generated from Binance spot `BTCUSDT` klines and exported with the ticker value `BTCUSD`.
Times are UTC.

## Files

- `data/BTCUSD_1m_forextester_2019_to_now.csv` - ForexTester-compatible 1-minute OHLCV data.
- `btcusd_forextester.py` - Downloader and converter used to generate the CSV.
- `tests/test_forextester_converter.py` - Unit tests for timestamp and row formatting.

## Data Range

- Start: `2019-09-01 00:00:00 UTC`
- Latest row in the current committed file: `2026-04-26 05:05:00 UTC`
- Interval: `1m`
- Source symbol: `BTCUSDT`
- Export ticker: `BTCUSD`

## CSV Format

The CSV has no header row. Each row uses this field order:

```text
<TICKER>,<DTYYYYMMDD>,<TIME>,<OPEN>,<HIGH>,<LOW>,<CLOSE>,<VOL>
```

Example:

```csv
BTCUSD,20190901,000000,9588.74000000,9590.93000000,9579.34000000,9579.62000000,22.38426100
```

Field notes:

- `DTYYYYMMDD` is the UTC date, for example `20190901`.
- `TIME` is the UTC time in `HHMMSS`, for example `000000`.
- `VOL` is Binance base asset volume for the 1-minute candle.

## Downloading From GitHub

The CSV is stored with Git LFS because it is larger than GitHub's regular file size limit.

Install Git LFS before cloning:

```bash
git lfs install
git clone https://github.com/i-zrhe2016/btcusd-forextester-data.git
cd btcusd-forextester-data
git lfs pull
```

## Regenerating The CSV

Run:

```bash
python3 btcusd_forextester.py \
  --start 2019-09-01 \
  --output data/BTCUSD_1m_forextester_2019_to_now.csv
```

Useful options:

- `--end 2026-04-26T00:00:00Z` to stop at a specific UTC datetime.
- `--header` to include a header row.
- `--no-live` to skip same-day API candles and use only archived files.
- `--output-symbol BTCUSD` to change the exported ticker column.

## Validation

Run the formatter tests:

```bash
python3 -m unittest tests/test_forextester_converter.py
```

The committed CSV was checked for:

- 8 columns per row.
- `YYYYMMDD` date format.
- `HHMMSS` time format.
- No duplicate timestamps.
- Strictly increasing timestamps.

## Notes

- This is not financial advice.
- Binance `BTCUSDT` data is used as a BTCUSD proxy. If strict BTC-USD exchange data is required, regenerate with a different source.
- The repository is private unless changed in GitHub settings.
