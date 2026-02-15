# Upbit 9AM Momentum Scanner

CLI tool to rank high-momentum KRW markets on Upbit using public ticker data.

## What it does

- Pulls all `KRW-*` markets from Upbit.
- Fetches ticker data in batches.
- Filters low-liquidity markets by 24h traded KRW notional.
- Computes a momentum score from:
  - signed daily change rate,
  - current location in today's high/low range,
  - liquidity term.

## Usage

```bash
python scanner.py
python scanner.py --top 25 --min-notional-krw 10000000000
python scanner.py --json
```

## Notes

- Upbit daily candles roll over at 09:00 KST; this scanner is intended to be run around that session reset window.
- Uses only public endpoints and does not require API keys.
