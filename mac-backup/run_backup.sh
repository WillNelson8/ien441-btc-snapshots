#!/bin/bash
# Mac backup for the daily 9am ET order book snapshot.
# macOS runs this at 8:00 am Central (= 9:00 am Eastern) if the Mac is on.
# If the Mac was asleep and wakes up later, macOS runs it on wake; we only keep the
# snapshot if it is still close to 9am Eastern (13:55 to 14:40 UTC), otherwise we skip.

cd "$HOME/ien441-btc-snapshots/mac-backup" || exit 1
now=$(date -u +%H%M)
if [ "$now" -lt 1355 ] || [ "$now" -gt 1440 ]; then
  echo "$(date): not near 9am Eastern (UTC $now), skipping" >> backup.log
  exit 0
fi
# collect_books.py saves into ./data/ (here: mac-backup/data/)
/opt/anaconda3/bin/python3 ../collect_books.py >> backup.log 2>&1
echo "$(date): done" >> backup.log
