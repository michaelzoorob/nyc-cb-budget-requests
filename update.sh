#!/bin/bash
# Rebuild every fiscal year's page and redeploy to Vercel.
#
#   ./update.sh               full rebuild: refreshes the latest year's Register from
#                             NYC Open Data and re-parses the PDF years
#   REUSE=1 ./update.sh       reuse parsed PDFs and downloaded Registers; use this when
#                             only committee_labels.csv or the code after the PDF parse
#                             changed (a parser change needs the full rebuild)
#   DATA=/some/dir ./update.sh
#
# Code runs from pipeline/. Downloads and intermediate CSVs go to the data directory
# (default ~/Downloads). The latest year is the site root (index.html); earlier years
# go to fy<YEAR>/index.html. The years themselves are listed in pipeline/shared.py.
set -e
PROJ="$(cd "$(dirname "$0")" && pwd)"
PIPELINE="$PROJ/pipeline"
DATA="${DATA:-$HOME/Downloads}"
YEARS=$(cd "$PIPELINE" && python3 -c "from shared import YEARS; print(' '.join(YEARS))")
LATEST=${YEARS%% *}

cd "$DATA"
if [ -z "$REUSE" ]; then
  echo "Refreshing the FY$LATEST Register from NYC Open Data..."
  rm -f "Register_FY${LATEST}_allboards.csv"
fi
for fy in $YEARS; do
  echo "== FY$fy =="
  python3 "$PIPELINE/build_all_boards.py" --fy "$fy" ${REUSE:+--reuse-parsed}
  if [ "$fy" = "$LATEST" ]; then out="$PROJ/index.html"; else mkdir -p "$PROJ/fy$fy"; out="$PROJ/fy$fy/index.html"; fi
  python3 "$PIPELINE/generate_cb2_html.py" --fy "$fy" "CB FY$fy Requests (all boards, detailed, 2-stage).csv" "$out"
done
# /fy<LATEST>/ forwards to the root, so a link naming the latest year explicitly keeps
# working. When a newer year is added, the loop above overwrites it with a real page.
mkdir -p "$PROJ/fy$LATEST"
cat > "$PROJ/fy$LATEST/index.html" <<EOF
<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><link rel="icon" href="data:,"><title>FY$LATEST Community Board Budget Requests</title>
<script>location.replace("/"+location.search+location.hash)</script></head>
<body><a href="/">FY$LATEST is the latest year. Continue to the dashboard.</a></body></html>
EOF

echo "Deploying to Vercel..."
cd "$PROJ"
vercel --prod --yes
echo
echo "Done -> https://cb2-budget-requests-fy2027.vercel.app"
