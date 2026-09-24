#!/bin/bash
# Rebuild every fiscal year's page and redeploy to Vercel.
#
#   ./update.sh               full rebuild: refreshes the latest year's Register from
#                             NYC Open Data and re-parses the PDF years
#   REUSE=1 ./update.sh       reuse parsed PDFs and downloaded Registers; use this when
#                             only the code or committee_labels.csv changed
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

echo "Deploying to Vercel..."
cd "$PROJ"
vercel --prod --yes
echo
echo "Done -> https://cb2-budget-requests-fy2027.vercel.app"
