# IEN 441: daily BTC order book snapshots

Every day at 9:00 am Eastern, GitHub runs `collect_books.py`, which saves the BTC/USD sell orders
(within 2% of the price) from Coinbase, Kraken, Gemini, and Bitstamp to `data/snapshot_<date>_<time>.json`.

Each file holds, for each exchange: the mid price, best bid, best ask, and a list of asks as [price, BTC size],
cheapest first.

Run it by hand: Actions tab > Daily 9am snapshot > Run workflow.
