#!/bin/bash
# Rebuild every fiscal year's page. Vercel deploys main from GitHub, so the rebuilt
# pages go live when a pull request with them merges into main.
#
#   ./update.sh               full rebuild: refreshes the latest year's Register from
#                             NYC Open Data and re-parses the PDF years
#   REUSE=1 ./update.sh       reuse parsed PDFs and downloaded Registers; use this when
#                             only committee_labels.csv or the code after the PDF parse
#                             changed (a parser change needs the full rebuild)
#   DATA=/some/dir ./update.sh
#
# Code runs from pipeline/. Downloads and intermediate CSVs go to the data directory
# (default ~/Downloads). The latest year is /dashboard/ (dashboard/index.html); earlier years
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
done
# Every year must exist before these two: they link requests across years.
echo "Locating requests (parks and street intersections)..."
python3 "$PIPELINE/locate_requests.py" "$DATA"
python3 "$PIPELINE/enrich_years.py" "$DATA"
for fy in $YEARS; do
  if [ "$fy" = "$LATEST" ]; then mkdir -p "$PROJ/dashboard"; out="$PROJ/dashboard/index.html"; else mkdir -p "$PROJ/fy$fy"; out="$PROJ/fy$fy/index.html"; fi
  python3 "$PIPELINE/generate_cb2_html.py" --fy "$fy" "CB FY$fy Requests (all boards, detailed, 2-stage).csv" "$out"
done
# /fy<LATEST>/ forwards to /dashboard/, so a link naming the latest year explicitly keeps
# working. When a newer year is added, the loop above overwrites it with a real page.
python3 "$PIPELINE/build_summary.py" "$DATA" "$PROJ/summary/index.html"
mkdir -p "$PROJ/fy$LATEST"
cat > "$PROJ/fy$LATEST/index.html" <<EOF
<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><link rel="icon" href="data:,"><title>FY$LATEST Community Board Budget Requests</title>
<script>location.replace("/dashboard/"+location.search+location.hash)</script></head>
<body><a href="/dashboard/">FY$LATEST is the latest year. Continue to the dashboard.</a></body></html>
EOF

echo
echo "Pages rebuilt. Commit them on a branch and open a pull request."
echo "Vercel builds a preview for the pull request and deploys the site when it merges into main."
