@echo off
cd /d "%-dp0"

call venv\Scripts\activate.bat
python scrape_dlsite.py

git add data/sales_log.csv data/price_state.json
git commit -m "Update sales log (local PC)"
git push

REM ===== FANZA =====
call "C:\Users\semedia\Documents\my-sales-watcher-fanz\run_scrape_fanza.bat"
if errorlevel 1 (
    echo [WARN] FANZA side failed
)