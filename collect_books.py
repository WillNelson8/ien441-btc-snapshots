# collect_books.py
# Takes one snapshot of the BTC/USD order book on 4 exchanges and saves it as a JSON file.
# Run it once a day at 9:00 am Eastern time.
# Only the sell side (asks) within 2% of the price is kept, since the model only buys.

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


snapshot = {"time_utc": datetime.datetime.utcnow().isoformat(timespec="seconds"), "exchanges": {}}

for name, fetch in [("Coinbase", coinbase), ("Kraken", kraken), ("Gemini", gemini), ("Bitstamp", bitstamp)]:
    try:
        bids, asks = fetch()
        best_bid = max(p for p, s in bids)
        best_ask = min(p for p, s in asks)
        mid = (best_bid + best_ask) / 2
        asks = sorted(a for a in asks if a[0] <= mid * (1 + KEEP))   # cheapest first
        snapshot["exchanges"][name] = {"mid": mid, "best_bid": best_bid, "best_ask": best_ask,
                                       "asks": asks}                  # each ask = [price, BTC size]
        dollars = sum(p * s for p, s in asks)
        print(f"{name:9s} mid ${mid:,.2f}   {len(asks):5d} ask levels   ${dollars/1e6:,.1f}M within 2%")
    except Exception as e:
        snapshot["exchanges"][name] = {"error": str(e)}
        print(f"{name:9s} FAILED: {e}")

day = datetime.datetime.utcnow().strftime("%Y-%m-%d_%H%M")
os.makedirs("data", exist_ok=True)
fname = f"data/snapshot_{day}.json"
with open(fname, "w") as f:
    json.dump(snapshot, f)
print("saved", fname)
