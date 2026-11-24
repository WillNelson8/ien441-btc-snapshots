# make_levels_csv.py
# ------------------------------------------------------------------------------------------
# WHAT THIS DOES
#   Reads every snapshot in data/ and writes ONE file, levels.csv, with exactly what the
#   model needs: for each snapshot, each exchange, and each of the 10 price levels,
#   how many dollars of BTC are for sale (q) and the average price (before fees).
#
#   A price level is a band of prices above the mid price:
#     level 1 = 0% to 0.1% above mid, level 2 = 0.1% to 0.2%, ..., level 10 = 0.9% to 1.0%
#
#   The notebook adds each exchange's trading fee to the price, so fees are NOT in this file.
#
# COLUMNS
#   snapshot        name of the snapshot, e.g. 2026-11-23_1400 (date and time in UTC)
#   time_utc        exact time the snapshot was taken
#   exchange        Coinbase, Kraken, Gemini, or Bitstamp
#   mid             mid price of BTC on that exchange at that moment ($)
#   level           1 to 10
#   low_price       bottom of the level ($)
#   high_price      top of the level ($)
#   q_dollars       dollars of BTC for sale in the level  (this is q in the model)
#   btc_for_sale    BTC for sale in the level
#   avg_price       size-weighted average price in the level, before fees ($)
#
# Run:  python make_levels_csv.py        (GitHub also runs it after every new snapshot)
#       python make_levels_csv.py mac-backup/hourly/data levels_hourly.csv
#                                        (same thing for the Mac hourly backups)
# ------------------------------------------------------------------------------------------

import csv
import glob
import json
import os
import sys

LEVELS = 10
BAND_WIDTH = 0.001   # each level is 0.1% wide
FOLDER = sys.argv[1] if len(sys.argv) > 1 else "data"          # where the snapshots are
OUT = sys.argv[2] if len(sys.argv) > 2 else "levels.csv"       # file to write

rows = []
for path in sorted(glob.glob(f"{FOLDER}/snapshot_*.json")):
    name = os.path.basename(path).replace("snapshot_", "").replace(".json", "")
    with open(path) as f:
        snap = json.load(f)

    for exchange, book in snap["exchanges"].items():
        if "error" in book:          # that exchange failed in this snapshot, skip it
            continue
        mid = book["mid"]
        for k in range(1, LEVELS + 1):
            low = mid * (1 + BAND_WIDTH * (k - 1))
            high = mid * (1 + BAND_WIDTH * k)
            orders = [(p, s) for p, s in book["asks"] if low <= p < high]
            dollars = sum(p * s for p, s in orders)
            btc = sum(s for p, s in orders)
            avg = dollars / btc if btc > 0 else (low + high) / 2   # empty level: q = 0 anyway
            rows.append([name, snap["time_utc"], exchange, round(mid, 2), k, round(low, 2), round(high, 2),
                         round(dollars, 2), round(btc, 6), round(avg, 2)])

with open(OUT, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["snapshot", "time_utc", "exchange", "mid", "level", "low_price", "high_price",
                "q_dollars", "btc_for_sale", "avg_price"])
    w.writerows(rows)

print(f"{OUT} written: {len(rows)} rows from {len(set(r[0] for r in rows))} snapshots")
