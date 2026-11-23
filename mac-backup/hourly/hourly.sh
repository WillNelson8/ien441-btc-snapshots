#!/bin/bash
# Takes a snapshot every hour on the hour, 11 am to 9 pm (Mac local time), then stops.
# Files go to mac-backup/hourly/data/.
cd "$HOME/ien441-btc-snapshots/mac-backup/hourly" || exit 1
for h in 11 12 13 14 15 16 17 18 19 20 21; do
  target=$(date -j -f "%H:%M:%S" "$h:00:00" +%s)
  now=$(date +%s)
  if [ "$now" -gt $((target + 300)) ]; then continue; fi      # this hour already passed
  if [ "$now" -lt "$target" ]; then sleep $((target - now)); fi
  echo "=== $(date) ===" >> hourly.log
  /opt/anaconda3/bin/python3 ../../collect_books.py >> hourly.log 2>&1
done
echo "=== finished $(date) ===" >> hourly.log
