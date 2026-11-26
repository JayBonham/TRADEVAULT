#!/bin/sh
# Fresh gold futures data for build_killshot.py (Yahoo keeps 1-minute bars for ~30 days only, so the
# downloaded files are kept in the repo: the game's charts can always be rebuilt from them).
cd "$(dirname "$0")/data" || exit 1
now=$(date +%s)
for w in 0 1 2 3; do p2=$((now - w*7*86400)); p1=$((p2 - 7*86400))
  curl -s -A "Mozilla/5.0" "https://query1.finance.yahoo.com/v8/finance/chart/GC=F?interval=1m&period1=$p1&period2=$p2" -o "gc1m_$(date -r $p2 +%Y%m%d).json"; done
curl -s -A "Mozilla/5.0" "https://query1.finance.yahoo.com/v8/finance/chart/GC=F?interval=1d&range=2y" -o gc1d.json
curl -s -A "Mozilla/5.0" "https://query1.finance.yahoo.com/v8/finance/chart/GC=F?interval=5m&range=60d" -o gc5m.json
