@echo off
cd /d "%-dp0"

call venv\Scripts\activate.bat
python scrape_dlsite.py

git add data/sales_log.csv data/price_state.json
git commit -m "Update sales log (local PC)"
git push