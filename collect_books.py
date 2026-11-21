# collect_books.py
# ------------------------------------------------------------------------------------------
# WHAT THIS DOES
#   Takes one snapshot of the BTC/USD order book on 4 exchanges (Coinbase, Kraken, Gemini,
#   Bitstamp) and saves it as a JSON file in the data/ folder.
#
#   An order book is the list of people offering to sell BTC: each line is a price and how
#   much BTC is for sale at that price. Our model only BUYS, so we only keep the sell side
#   ("asks"), and only the part within 2% of the current price (that is all the model uses).
#
# WHEN IT RUNS
#   GitHub runs this automatically every day at 9:00 am Eastern time
#   (see .github/workflows/daily-snapshot.yml). It can also be run by hand.
#
# WHAT GETS SAVED (one file per run)
#   time_utc            when the snapshot was taken
#   for each exchange:
#     mid               the price halfway between the best buy and best sell offer
#     best_bid          highest price someone will pay for BTC
#     best_ask          lowest price someone will sell BTC for
#     asks              list of [price in $, BTC for sale], cheapest first
#   If an exchange fails to answer, its entry holds "error" instead, and the others are still saved.
# ------------------------------------------------------------------------------------------

import json
import os
import datetime
import requests

KEEP = 0.02  # keep sell orders up to 2% above the mid price


def get(url):
    # download a web page and turn the JSON into Python lists/dicts
    r = requests.get(url, timeout=30, headers={"User-Agent": "ien441-class-project"})
    r.raise_for_status()
    return r.json()


# Each exchange's public order book page has a slightly different format,
# so each one gets its own small function. Every function returns two lists:
#   bids = [(price, BTC size), ...]  people wanting to buy
#   asks = [(price, BTC size), ...]  people wanting to sell (what we care about)


def coinbase():
    book = get("https://api.exchange.coinbase.com/products/BTC-USD/book?level=2")
    bids = [(float(p), float(s)) for p, s, _ in book["bids"]]
    asks = [(float(p), float(s)) for p, s, _ in book["asks"]]
    return bids, asks


def kraken():
    book = get("https://api.kraken.com/0/public/Depth?pair=XBTUSD&count=500")
    data = list(book["result"].values())[0]
    bids = [(float(p), float(s)) for p, s, _ in data["bids"]]
    asks = [(float(p), float(s)) for p, s, _ in data["asks"]]
    return bids, asks


def gemini():
    book = get("https://api.gemini.com/v1/book/btcusd?limit_bids=50&limit_asks=0")
    bids = [(float(o["price"]), float(o["amount"])) for o in book["bids"]]
    asks = [(float(o["price"]), float(o["amount"])) for o in book["asks"]]
    return bids, asks


def bitstamp():
    book = get("https://www.bitstamp.net/api/v2/order_book/btcusd/")
    bids = [(float(p), float(s)) for p, s in book["bids"]]
    asks = [(float(p), float(s)) for p, s in book["asks"]]
    return bids, asks


# ---------------- main part: ask every exchange and save the results ----------------

snapshot = {"time_utc": datetime.datetime.utcnow().isoformat(timespec="seconds"), "exchanges": {}}

for name, fetch in [("Coinbase", coinbase), ("Kraken", kraken), ("Gemini", gemini), ("Bitstamp", bitstamp)]:
    try:
        bids, asks = fetch()
        # the mid price is halfway between the best buy offer and the best sell offer
        best_bid = max(p for p, s in bids)
        best_ask = min(p for p, s in asks)
        mid = (best_bid + best_ask) / 2
        # keep only sell orders priced within 2% above the mid price, cheapest first
        asks = sorted(a for a in asks if a[0] <= mid * (1 + KEEP))
        snapshot["exchanges"][name] = {"mid": mid, "best_bid": best_bid, "best_ask": best_ask,
                                       "asks": asks}                  # each ask = [price, BTC size]
        dollars = sum(p * s for p, s in asks)
        print(f"{name:9s} mid ${mid:,.2f}   {len(asks):5d} ask levels   ${dollars/1e6:,.1f}M within 2%")
    except Exception as e:
        # if one exchange is down, record the error and keep going with the others
        snapshot["exchanges"][name] = {"error": str(e)}
        print(f"{name:9s} FAILED: {e}")

# name the file by date and time (UTC), e.g. data/snapshot_2026-11-21_1400.json
day = datetime.datetime.utcnow().strftime("%Y-%m-%d_%H%M")
os.makedirs("data", exist_ok=True)
fname = f"data/snapshot_{day}.json"
with open(fname, "w") as f:
    json.dump(snapshot, f)
print("saved", fname)
