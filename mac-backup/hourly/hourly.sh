#!/bin/bash
# Takes a snapshot every hour on the hour, 8 am to 6 pm Central (= 9 am to 7 pm Eastern), then stops.
# If today's window is already over when it starts, it waits and runs tomorrow instead.
# Files go to mac-backup/hourly/data/. After the last one it updates levels_hourly.csv and pushes to GitHub.
# Keep the Mac plugged in with the lid open.
cd "$HOME/ien441-btc-snapshots/mac-backup/hourly" || exit 1
day=$(date +%Y-%m-%d)
last=$(date -j -f "%Y-%m-%d %H:%M:%S" "$day 18:05:00" +%s)
if [ "$(date +%s)" -gt "$last" ]; then day=$(date -v+1d +%Y-%m-%d); fi   # too late today, do tomorrow
echo "=== started $(date), collecting on $day ===" >> hourly.log
for h in 08 09 10 11 12 13 14 15 16 17 18; do
  target=$(date -j -f "%Y-%m-%d %H:%M:%S" "$day $h:00:00" +%s)
  now=$(date +%s)
  if [ "$now" -gt $((target + 300)) ]; then continue; fi      # this hour already passed
  while [ "$(date +%s)" -lt "$target" ]; do sleep 30; done      # check the clock every 30 s (a long sleep runs late if the Mac sleeps)
  echo "=== $(date) ===" >> hourly.log
  /opt/anaconda3/bin/python3 ../../collect_books.py >> hourly.log 2>&1
done
echo "=== finished $(date) ===" >> hourly.log

# After the last snapshot: rebuild levels_hourly.csv and push it, with the new snapshots, to GitHub
# so the Colab notebook (Cell 10) always has today's hours.
cd "$HOME/ien441-btc-snapshots" || exit 1
{
  /opt/anaconda3/bin/python3 make_levels_csv.py mac-backup/hourly/data levels_hourly.csv
  git add mac-backup/hourly/data/*.json levels_hourly.csv
  git commit -m "Hourly snapshots $day" || echo "nothing new to commit"
  if git pull --rebase --autostash && git push; then   # --autostash: other local edits do not block the pull
    echo "=== pushed to GitHub $(date) ==="
  else
    echo "=== PUSH FAILED $(date) ==="
  fi
} >> mac-backup/hourly/hourly.log 2>&1
