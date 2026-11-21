# IEN 441: Optimal Cross-Venue Execution of BTC

Team project: a mixed-integer program that finds the cheapest way to buy a target amount of BTC
across Coinbase, Kraken, Gemini, and Bitstamp over 10 one-hour rounds (9 am to 7 pm Eastern),
starting with all cash at Coinbase.

## What's in here

| Folder / file | What it is |
| --- | --- |
| `paper/MODEL.md` | **Start here:** the model (LP) on one page, with a plain-English line for each constraint. |
| `paper/` | The full paper as PDF (readable on GitHub) and Word. |
| `colab/btc_routing.ipynb` | The Colab notebook: builds the price levels, solves the model, prints the path and cost breakdown, runs the experiments. |
| `colab/btc_routing_colab.py` | Same notebook as plain text, one `# %% CELL` block per Colab cell. |
| `collect_books.py` | Takes one order book snapshot from all 4 exchanges. |
| `data/` | The daily 9 am snapshots (one JSON file per day). |
| `.github/workflows/daily-snapshot.yml` | Runs `collect_books.py` automatically every day at 9 am Eastern. |
| `mac-backup/` | Backup script that takes the same snapshot from a Mac. |

## Open the notebook in Colab

1. Go to colab.research.google.com, then **File > Open notebook > GitHub**.
2. Tick **Include private repos** (and sign in to GitHub if asked).
3. Pick `WillNelson8/ien441-btc-snapshots` and open `colab/btc_routing.ipynb`.
4. Download a snapshot from `data/` (click the file, then the download button).
5. Run the cells in order. Cell 2 asks you to upload the snapshot.

Colab does not save back to GitHub on its own. Use **File > Save a copy in GitHub** to save changes.

## Snapshots

Every day at 9:00 am Eastern, GitHub runs `collect_books.py`, which saves the BTC/USD sell orders
(within 2% of the price) to `data/snapshot_<date>_<time>.json` (time in UTC; 1400 = 9:00 am Eastern).
Run it by hand: **Actions tab > Daily 9am snapshot > Run workflow**.

Each file holds, for each exchange: the mid price, best bid, best ask, and a list of asks as
[price, BTC size], cheapest first.

The snapshots dated `2026-11-21_0115`, `_0117` (8 pm Eastern) and `_1718` (12 pm Eastern) are test
snapshots, not 9 am ones.

## Placeholders to replace

In notebook cell 3: Bitstamp's taker fee and the $25 transfer fee are placeholders until someone with
exchange accounts confirms the real values.
