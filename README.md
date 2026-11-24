# IEN 441: Optimal Cross-Venue Execution of BTC

Team project: a mixed-integer program that finds the cheapest way to buy a target amount of BTC
across Coinbase, Kraken, Gemini, and Bitstamp over 10 one-hour rounds (9 am to 7 pm Eastern),
starting with all cash at Coinbase.

## What's in here

| Folder / file | What it is |
| --- | --- |
| `paper/MODEL.md` | **Start here:** the model on one page, with a plain-English line for each constraint. |
| `paper/` | The full paper as PDF (readable on GitHub) and Word. |
| `colab/btc_routing.ipynb` | The Colab notebook: loads the price levels, solves the model, prints the path and cost breakdown, runs the experiments. |
| `colab/btc_routing_colab.py` | Same notebook as plain text, one `# %% CELL` block per Colab cell. |
| `levels.csv` | **The file the model runs on:** every 9 am snapshot split into 10 price levels per exchange (q = dollars for sale, average price). Rebuilt automatically after each snapshot. |
| `levels_hourly.csv` | The same for the hourly Mac snapshots (used by notebook Cell 10). Rebuilt and pushed by the Mac after the last snapshot each day. |
| `results/hourly_results.csv` | Model results for every hourly snapshot (100 BTC, refill rate 0.5). |
| `make_levels_csv.py` | Builds `levels.csv` from `data/`, or `levels_hourly.csv` from `mac-backup/hourly/data/`. |
| `collect_books.py` | Takes one order book snapshot from all 4 exchanges. |
| `data/` | The daily 9 am Eastern snapshots (one JSON file per day). |
| `mac-backup/hourly/` | `hourly.sh` takes a snapshot every hour, 9 am to 7 pm Eastern, from a Mac; files go to `mac-backup/hourly/data/`. |
| `.github/workflows/daily-snapshot.yml` | Takes the 9 am snapshot on GitHub and rebuilds `levels.csv`. |
| `trigger/` | A scheduled Claude routine pushes `trigger/run.txt` at 8:50 am Eastern, which starts the workflow on time. |

## Open the notebook in Colab

1. Go to colab.research.google.com, then **File > Open notebook > GitHub**.
2. Tick **Include private repos** (and sign in to GitHub if asked).
3. Pick `WillNelson8/ien441-btc-snapshots` and open `colab/btc_routing.ipynb`.
4. One time only: make a GitHub fine-grained token (only this repo, Contents = Read-only) and add it
   in Colab under the key icon (Secrets) as `GITHUB_TOKEN`, with Notebook access on.
5. Run the cells in order. Cell 2 reads `levels.csv` straight from GitHub (or asks you to upload it
   if the token is missing) and uses the newest snapshot (change `SNAPSHOT` there to pick another).
   Cell 9 runs every 9 am snapshot and averages the results. Cell 10 runs every hourly snapshot.

Colab does not save back to GitHub on its own. Use **File > Save a copy in GitHub** to save changes.

## Snapshots

Every day at 9:00 am Eastern, GitHub runs `collect_books.py`, which saves the BTC/USD sell orders
(within 2% of the price) to `data/snapshot_<date>_<time>.json` (time in UTC; 1400 = 9:00 am Eastern).
Run it by hand: **Actions tab > Daily 9am snapshot > Run workflow**.

Each file holds, for each exchange: the mid price, best bid, best ask, and a list of asks as
[price, BTC size], cheapest first.

The hourly Mac backup must be started each evening for the next day (Mac plugged in, lid open):

    cd ~/ien441-btc-snapshots/mac-backup/hourly && nohup caffeinate -is ./hourly.sh >/dev/null 2>&1 &
