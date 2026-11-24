# ==========================================================================================
# IEN 441 - Optimal Cross-Venue Execution of BTC
# Google Colab notebook, one cell per block below.
# Paste each block that starts with "# %% CELL" into its own Colab cell and run them in order.
# ==========================================================================================


# %% CELL 1 - Install and import the tools ------------------------------------------------
# PuLP builds the optimization model and solves it with the free CBC solver.
# (In Colab, the line below installs PuLP. The "!" means "run this as a terminal command".)
# Use the exact version this notebook was tested with. If Colab already had another
# version loaded, do Runtime > Restart session after this cell, then run all again.
# !pip install pulp==3.3.2

import pulp
import pandas as pd
print("PuLP version:", pulp.__version__)


# %% CELL 2 - Load the price levels (levels.csv) -----------------------------------------
# levels.csv is in the GitHub repo "ien441-btc-snapshots". It holds every snapshot already
# split into 10 price levels per exchange (made by make_levels_csv.py, updated every day).
#
# This cell reads it straight from GitHub, so you never download or upload it.
# The repo is private, so Colab needs a GitHub token (set up once):
#   1) On GitHub: Settings > Developer settings > Fine-grained tokens > Generate new token.
#      Repository access: only ien441-btc-snapshots.  Permissions: Contents = Read-only.
#   2) In Colab: click the key icon on the left (Secrets), add a secret named GITHUB_TOKEN,
#      paste the token as its value, and turn on "Notebook access".
# If that does not work, the cell opens a file picker so you can upload the CSV instead.

import io

REPO = "WillNelson8/ien441-btc-snapshots"

def load_csv(name):
    # read a CSV from the GitHub repo (in Colab) or from this folder (on a laptop)
    try:
        from google.colab import userdata, files      # only works inside Colab
    except ImportError:
        return pd.read_csv(name)                      # on a laptop: the file next to this notebook
    try:
        import requests
        token = userdata.get("GITHUB_TOKEN")
        url = f"https://raw.githubusercontent.com/{REPO}/main/{name}"
        r = requests.get(url, headers={"Authorization": f"token {token}"}, timeout=30)
        r.raise_for_status()
        print(f"Loaded {name} from GitHub")
        return pd.read_csv(io.StringIO(r.text))
    except Exception as e:
        print(f"Could not read {name} from GitHub ({e}). Upload it instead:")
        uploaded = files.upload()                     # opens a file picker
        return pd.read_csv(io.BytesIO(list(uploaded.values())[0]))

levels_df = load_csv("levels.csv")
SNAPSHOTS = sorted(levels_df["snapshot"].unique())
print("Snapshots in the file (date_time in UTC; 1400 = 9:00 am Eastern):")
for name in SNAPSHOTS:
    print("  ", name)

# Pick the snapshot to use. The last one in the list is the newest.
SNAPSHOT = SNAPSHOTS[-1]
print("\nUsing snapshot:", SNAPSHOT)


# %% CELL 3 - Settings you can change ------------------------------------------------------

EXCHANGES = ["Coinbase", "Kraken", "Gemini", "Bitstamp"]
START = "Coinbase"          # the whole budget starts here

ROUNDS = list(range(1, 11))  # 10 one-hour rounds: round 1 = 9am, ..., round 10 = 6pm
HOURS = {1: "9am", 2: "10am", 3: "11am", 4: "12pm", 5: "1pm",
         6: "2pm", 7: "3pm", 8: "4pm", 9: "5pm", 10: "6pm"}

LEVELS = list(range(1, 11))  # 10 price levels (bands)

# Taker fee = the % fee an exchange charges when you buy right away.
# Fees go down as your 30-day trading volume goes up, so we pick ONE volume for every exchange:
# a desk that trades about $25M of crypto per 30 days. Each number is the tier that $25M lands in,
# from each exchange's own fee page (checked Nov 22, 2026):
#   Coinbase Exchange  $15M-$75M tier   help.coinbase.com/en/exchange/trading-and-funding/exchange-fees
#   Kraken Pro         Tier 12 ($10M+)  kraken.com/pro/fees
#   Gemini ActiveTrader $20M tier       gemini.com/fees/activetrader-fee-schedule
#   Bitstamp           > $20M tier      bitstamp.net/fee-schedule (same in the Nov 24, 2026 update)
TAKER_FEE = {
    "Coinbase": 0.0016,     # 0.16%
    "Kraken":   0.0010,     # 0.10%
    "Gemini":   0.0005,     # 0.05%
    "Bitstamp": 0.0010,     # 0.10%
}

# Cash moves between exchanges by USD bank wire.
# Cost of one transfer = withdrawal fee at the sending exchange + deposit fee at the receiving one.
WIRE_OUT = {                # flat $ fee to send a USD wire out of each exchange
    "Coinbase": 25.0,       # Coinbase Exchange fee page: wire withdrawal $25
    "Kraken":   4.0,        # Kraken support "Cash withdrawal fees": FedWire $4
    "Gemini":   25.0,       # Gemini support: $25 wire withdrawal processing fee
    "Bitstamp": 25.0,       # Bitstamp: 0.1% of the amount, minimum $25. We use the $25 minimum
}                           #   (the model never sends cash out of Bitstamp, so this rarely matters)
WIRE_IN = {                 # flat $ fee to receive a USD wire at each exchange
    "Coinbase": 10.0,       # Coinbase Exchange fee page: wire deposit $10
    "Kraken":   0.0,        # Kraken support "Cash deposit options": FedWire deposit free
    "Gemini":   0.0,        # Gemini support: no fee on wire deposits
    "Bitstamp": 300.0,      # Bitstamp: 0.05% of the deposit, max $300. Any deposit of $600K or more
}                           #   pays exactly $300, so we use $300 (a little high for small deposits)

# F[v,u] = flat fee for one transfer from v to u (the F in the model, one per route)
TRANSFER_FEE = {(v, u): WIRE_OUT[v] + WIRE_IN[u] for v in EXCHANGES for u in EXCHANGES if v != u}

GOAL_BTC = 100              # D: how much BTC the desk must buy
REFILL = 0.5                # rho: share of each price level that comes back every hour (0 to 1)


# %% CELL 4 - Get p and q for each exchange and level -------------------------------------
# From levels.csv, for the chosen snapshot:
#   q = dollars of BTC for sale in that level
#   p = average price of that level, plus the exchange's taker fee

def make_books(snapshot):
    rows = levels_df[levels_df["snapshot"] == snapshot]
    books = {}
    for v in EXCHANGES:
        books[v] = {}
        for k in LEVELS:
            r = rows[(rows["exchange"] == v) & (rows["level"] == k)].iloc[0]
            books[v][k] = {"q": r["q_dollars"],
                           "p": r["avg_price"] * (1 + TAKER_FEE[v]),
                           "p_no_fee": r["avg_price"]}
    return books

books = make_books(SNAPSHOT)

# show the levels as a table: dollars for sale ($M) at each level, per exchange
table = pd.DataFrame({v: {k: round(books[v][k]["q"] / 1e6, 2) for k in LEVELS} for v in EXCHANGES})
table.index.name = "level"
print("Dollars for sale at each level ($ millions), snapshot", SNAPSHOT)
print(table)


# %% CELL 5 - The model ---------------------------------------------------------------------
# This is the mixed-integer program from the paper, written in PuLP.
# solve_model(goal, refill, budget, coinbase_only) returns the plan and its cost.

def solve_model(goal, refill, budget, coinbase_only=False, relax=False):
    model = pulp.LpProblem("btc_routing", pulp.LpMinimize)
    pairs = [(v, u) for v in EXCHANGES for u in EXCHANGES if v != u]   # 12 transfer routes
    M = budget                                                        # big number = total cash

    # ----- decision variables -----
    # x[v,k,t] = dollars spent at exchange v, level k, round t
    x = {v: {k: {t: pulp.LpVariable(f"x_{v}_{k}_{t}", lowBound=0) for t in ROUNDS}
                 for k in LEVELS} for v in EXCHANGES}
    # y[v,u,t] = dollars sent from exchange v to exchange u in round t
    y = {(v, u): {t: pulp.LpVariable(f"y_{v}_{u}_{t}", lowBound=0) for t in ROUNDS} for (v, u) in pairs}
    # B[v,t] = cash left at exchange v at the end of round t
    B = {v: {t: pulp.LpVariable(f"B_{v}_{t}", lowBound=0) for t in ROUNDS} for v in EXCHANGES}
    # w[v,u,t] = 1 if any money is sent from v to u in round t (binary)
    # (relax=True lets w be any number from 0 to 1: the "LP relaxation")
    w_type = pulp.LpContinuous if relax else pulp.LpBinary
    w = {(v, u): {t: pulp.LpVariable(f"w_{v}_{u}_{t}", lowBound=0, upBound=1, cat=w_type) for t in ROUNDS}
         for (v, u) in pairs}

    # ----- objective: dollars spent on BTC + transfer fees -----
    model += (pulp.lpSum(x[v][k][t] for v in EXCHANGES for k in LEVELS for t in ROUNDS)
              + pulp.lpSum(TRANSFER_FEE[pr] * w[pr][t] for pr in pairs for t in ROUNDS))

    # ----- (4) start: all cash at Coinbase, $0 elsewhere -----
    start_cash = {v: (budget if v == START else 0) for v in EXCHANGES}

    for v in EXCHANGES:
        for t in ROUNDS:
            # ----- (1) flow: cash now = cash before + arrivals from last round - sent - spent -----
            cash_before = start_cash[v] if t == 1 else B[v][t - 1]
            arrived = pulp.lpSum(y[(u, v)][t - 1] for u in EXCHANGES if u != v) if t > 1 else 0
            sent = pulp.lpSum(y[(v, u)][t] for u in EXCHANGES if u != v)
            spent = pulp.lpSum(x[v][k][t] for k in LEVELS)
            model += B[v][t] == cash_before + arrived - sent - spent

    for v in EXCHANGES:
        for k in LEVELS:
            q = books[v][k]["q"]
            for t in ROUNDS:
                # ----- (2a) refill: bought so far <= 9am amount + refills since -----
                model += pulp.lpSum(x[v][k][s] for s in ROUNDS if s <= t) <= q + refill * (t - 1) * q
                # ----- (2b) full-level cap: never buy more than a full level in one round -----
                model += x[v][k][t] <= q

    # ----- (3) target: BTC bought >= goal -----
    model += pulp.lpSum(x[v][k][t] * (1 / books[v][k]["p"])
                        for v in EXCHANGES for k in LEVELS for t in ROUNDS) >= goal

    # ----- (5) fee switch: if money is sent (y > 0) then w = 1 -----
    for pr in pairs:
        for t in ROUNDS:
            model += y[pr][t] <= M * w[pr][t]
            if coinbase_only:
                model += y[pr][t] == 0            # baseline: no transfers allowed

    model.solve(pulp.PULP_CBC_CMD(msg=False))
    status = pulp.LpStatus[model.status]
    if status != "Optimal":
        return {"status": status}

    # ----- collect the answer in plain Python numbers -----
    buys = {(v, k, t): x[v][k][t].value() for v in EXCHANGES for k in LEVELS for t in ROUNDS
            if x[v][k][t].value() > 0.01}
    moves = {(v, u, t): y[(v, u)][t].value() for (v, u) in pairs for t in ROUNDS
             if y[(v, u)][t].value() > 0.01}
    cash = {(v, t): B[v][t].value() for v in EXCHANGES for t in ROUNDS}
    n_transfers = len(moves)      # count the transfers that actually moved money
    return {"status": status, "cost": pulp.value(model.objective), "buys": buys, "moves": moves,
            "cash": cash, "n_transfers": n_transfers, "budget": budget,
            "variables": len(model.variables()), "constraints": len(model.constraints)}


def run(goal, refill):
    # 1) Baseline: buy everything at Coinbase (huge budget so cash is never the problem)
    base = solve_model(goal, refill, budget=1e12, coinbase_only=True)
    if base["status"] != "Optimal":
        return None, None
    # 2) Smart plan: budget = 120% of the baseline cost, all of it starting at Coinbase
    best = solve_model(goal, refill, budget=1.2 * base["cost"])
    return best, base


# %% CELL 6 - Run it and show the path and the cost breakdown ------------------------------

def show(best, base):
    if best is None or best["status"] != "Optimal":
        print("No plan found: the goal is bigger than what these order books can supply.")
        return
    print(f"Model size: {best['variables']} variables, {best['constraints']} constraints\n")

    # ---- the path, hour by hour ----
    print("PATH THE MODEL TOOK")
    for t in ROUNDS:
        lines = []
        for v in EXCHANGES:
            spent = sum(d for (vv, k, tt), d in best["buys"].items() if vv == v and tt == t)
            if spent > 0:
                btc = sum(d / books[v][k]["p"] for (vv, k, tt), d in best["buys"].items() if vv == v and tt == t)
                lvls = sorted(k for (vv, k, tt) in best["buys"] if vv == v and tt == t)
                word = "level" if len(lvls) == 1 else "levels"
                lines.append(f"bought {btc:.2f} BTC at {v} ({word} {', '.join(map(str, lvls))})")
        for (v, u, tt), d in best["moves"].items():
            if tt == t:
                lines.append(f"sent ${d:,.0f} from {v} to {u} (arrives next hour, fee ${TRANSFER_FEE[(v, u)]:,.0f})")
        if lines:
            print(f"  {HOURS[t]:>5}: " + "; ".join(lines))

    # ---- the cost breakdown ----
    btc_total = sum(d / books[v][k]["p"] for (v, k, t), d in best["buys"].items())
    before_fees = sum(d / books[v][k]["p"] * books[v][k]["p_no_fee"] for (v, k, t), d in best["buys"].items())
    trading_fees = sum(best["buys"].values()) - before_fees
    best_price = min(books[v][1]["p_no_fee"] for v in EXCHANGES if books[v][1]["q"] > 0)
    at_best = btc_total * best_price
    transfer_fees = sum(TRANSFER_FEE[(v, u)] for (v, u, t) in best["moves"])

    print("\nCOST BREAKDOWN")
    print(f"  {btc_total:.2f} BTC at the best 9am price   ${at_best:,.0f}")
    print(f"  Extra for higher price levels      ${before_fees - at_best:,.0f}")
    print(f"  Trading fees                       ${trading_fees:,.0f}")
    print(f"  Transfer fees ({round(best['n_transfers'])})                  ${transfer_fees:,.0f}")
    print(f"  TOTAL                              ${best['cost']:,.0f}")
    print(f"\n  Coinbase only: ${base['cost']:,.0f}.   Saved: ${base['cost'] - best['cost']:,.0f}")

best, base = run(GOAL_BTC, REFILL)
show(best, base)


# %% CELL 7 - Experiments: order size x refill rate -----------------------------------------
# Runs the model for each order size and refill rate and shows how much routing saves.
# (Order sizes are in dollars and turned into BTC with the Coinbase 9am price.)

ORDER_SIZES = [100_000, 500_000, 1_000_000, 5_000_000, 10_000_000, 25_000_000]
REFILL_RATES = [0, 0.25, 0.5, 1]
rows_cb = levels_df[(levels_df["snapshot"] == SNAPSHOT) & (levels_df["exchange"] == "Coinbase")]
price = rows_cb["mid"].iloc[0]

rows = []
for size in ORDER_SIZES:
    for rho in REFILL_RATES:
        goal = size / price
        b, cb = run(goal, rho)
        if b is None or b["status"] != "Optimal":
            rows.append({"order $": size, "refill": rho, "result": "not enough BTC for sale"})
            continue
        rows.append({"order $": size, "refill": rho, "BTC": round(goal, 2),
                     "smart plan $": round(b["cost"]), "Coinbase only $": round(cb["cost"]),
                     "saved $": round(cb["cost"] - b["cost"]),
                     "saved %": round(100 * (cb["cost"] - b["cost"]) / cb["cost"], 3),
                     "transfers": round(b["n_transfers"])})

results = pd.DataFrame(rows)
print(results.to_string(index=False))


# %% CELL 8 - LP relaxation (optional) ------------------------------------------------------
# Same model, but w can be any number from 0 to 1 instead of only 0 or 1.
# Its cost is a lower bound on the true cost; the gap shows how much the flat fees matter.

relaxed = solve_model(GOAL_BTC, REFILL, budget=best["budget"], relax=True)
print(f"MIP cost:            ${best['cost']:,.2f}")
print(f"LP relaxation cost:  ${relaxed['cost']:,.2f}")
print(f"Gap:                 ${best['cost'] - relaxed['cost']:,.2f}")


# %% CELL 9 - Run every snapshot and average the results ------------------------------------
# For each snapshot in levels.csv: solve the model and the Coinbase-only baseline,
# then show the average savings and the lowest/highest day.
# Set USE to a list of snapshot names to pick only some (for example only the 9 am ones).

USE = [s for s in SNAPSHOTS if s.endswith("_1400")] or SNAPSHOTS   # 9 am ones if there are any
SIZE = 10_000_000          # order size in dollars
RHO = REFILL

per_day = []
for name in USE:
    books = make_books(name)                                    # the model reads this global
    mid = levels_df[(levels_df["snapshot"] == name) & (levels_df["exchange"] == "Coinbase")]["mid"].iloc[0]
    b, cb = run(SIZE / mid, RHO)
    if b is None or b["status"] != "Optimal":
        per_day.append({"snapshot": name, "result": "not enough BTC for sale"})
        continue
    per_day.append({"snapshot": name, "saved $": round(cb["cost"] - b["cost"]),
                    "saved %": round(100 * (cb["cost"] - b["cost"]) / cb["cost"], 4),
                    "transfers": round(b["n_transfers"])})

per_day = pd.DataFrame(per_day)
print(per_day.to_string(index=False))
if "saved %" in per_day:
    print(f"\nAverage saved: ${per_day['saved $'].mean():,.0f} ({per_day['saved %'].mean():.4f}%)")
    print(f"Lowest day:    ${per_day['saved $'].min():,.0f}     Highest day: ${per_day['saved $'].max():,.0f}")
    print(f"Days with a transfer: {(per_day['transfers'] > 0).sum()} of {len(per_day)}")
books = make_books(SNAPSHOT)   # put the chosen snapshot back for the other cells


# %% CELL 10 - Run every hourly snapshot (Mac backups) -----------------------------------
# The Mac takes a snapshot every hour from 9 am to 7 pm Eastern (mac-backup/hourly/).
# levels_hourly.csv holds those, split into price levels the same way as levels.csv.
# For each hour: solve the model as if the order started at that hour, compare with
# Coinbase only, and save the table as hourly_results.csv.

hourly_df = load_csv("levels_hourly.csv")
HOURLY = sorted(hourly_df["snapshot"].unique())
SIZE_BTC = GOAL_BTC        # order size (BTC), from Cell 3
RHO = REFILL               # refill rate, from Cell 3

daily_df = levels_df       # keep the 9 am data to put back at the end
levels_df = hourly_df      # make_books reads levels_df
rows = []
for name in HOURLY:
    books = make_books(name)                                    # the model reads this global
    utc = pd.to_datetime(hourly_df[hourly_df["snapshot"] == name]["time_utc"].iloc[0])
    eastern = utc.tz_localize("UTC").tz_convert("America/New_York")
    b, cb = run(SIZE_BTC, RHO)
    row = {"snapshot": name, "date": eastern.strftime("%Y-%m-%d"), "start (ET)": eastern.strftime("%I:%M %p")}
    if b is None or b["status"] != "Optimal":
        row["result"] = "not enough BTC for sale"
    else:
        row.update({"smart plan $": round(b["cost"]), "Coinbase only $": round(cb["cost"]),
                    "saved $": round(cb["cost"] - b["cost"]),
                    "saved %": round(100 * (cb["cost"] - b["cost"]) / cb["cost"], 3),
                    "transfers": b["n_transfers"],
                    "moves": ", ".join(f"{v} to {u} (round {t})" for (v, u, t) in b["moves"])})
    rows.append(row)
levels_df = daily_df       # put the 9 am data back for the other cells
books = make_books(SNAPSHOT)

hourly_results = pd.DataFrame(rows)
print(f"{SIZE_BTC} BTC, refill rate {RHO}")
print(hourly_results.drop(columns=["snapshot", "moves"]).to_string(index=False))
for day, g in hourly_results.dropna(subset=["saved $"]).groupby("date"):
    print(f"\n{day}: {len(g)} hours, average saved ${g['saved $'].mean():,.0f}, "
          f"lowest ${g['saved $'].min():,.0f}, highest ${g['saved $'].max():,.0f}")

hourly_results.to_csv("hourly_results.csv", index=False)
try:
    from google.colab import files
    files.download("hourly_results.csv")   # saves it to your computer
except ImportError:
    print("\nSaved hourly_results.csv")
