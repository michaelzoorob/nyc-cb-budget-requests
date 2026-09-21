#!/bin/bash
# Rebuild the all-59-board FY2027 dashboard and redeploy to Vercel.
# Run this whenever the data or the layout changes.
#
# Code lives in this repo (pipeline/); the data inputs and intermediate CSVs
# live in a scratch data directory, which defaults to ~/Downloads.
# Override with:  DATA=/path/to/data ./update.sh
set -e
PROJ="$(cd "$(dirname "$0")" && pwd)"
PIPELINE="$PROJ/pipeline"
DATA="${DATA:-$HOME/Downloads}"
COMBINED="CB FY2027 Requests (all boards, detailed, 2-stage).csv"

cd "$DATA"
echo "1/4  Pulling the FY2027 Register (all boards) from NYC Open Data..."
curl -s -o Register_FY2027_allboards.csv "https://data.cityofnewyork.us/resource/vn4m-mk4t.csv?\$select=publication,boro,board,priority,tracking_code,request,explanation,response,responded_by,responsible_agency&\$where=publication='20270217'%20OR%20publication='20260512'&\$limit=20000" -A research
echo "2/4  Fetching + parsing all 59 Statement PDFs and building each board (parallel)..."
python3 "$PIPELINE/build_all_boards.py"
echo "3/4  Generating the dashboard HTML..."
python3 "$PIPELINE/generate_cb2_html.py" "$COMBINED"
cp "CB2 FY2027 Requests and Agency Responses.html" "$PROJ/index.html"
echo "4/4  Deploying to Vercel..."
cd "$PROJ"
vercel --prod --yes
echo
echo "Done -> https://cb2-budget-requests-fy2027.vercel.app"
