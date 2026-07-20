@echo off
rem Ban tin chieu tu dong - chay boi Windows Task Scheduler 18:41 hang ngay.
rem Luong: pull snapshot moi (routine cloud day ~18:08) -> tai EOD that
rem -> cap nhat watchlist -> ban tin chieu (tu gui Telegram) -> health check
rem -> commit + push data/ de lich su ben vung.
rem LUU Y: file nay phai giu ASCII thuan tuy - cmd parse loi voi UTF-8 tieng Viet.
rem Duong dan repo lay tu vi tri file bat (%~dp0 = ...\Finance-duy\scripts\).

cd /d "%~dp0.."
set PYTHONIOENCODING=utf-8
set PY=C:\Users\Duy\AppData\Local\Programs\Python\Python312\python.exe
set BRANCH=claude/investment-news-aggregator-w81l70

echo ==== DAILY TASK %date% %time% ==== >> logs\daily_task.log

git pull origin %BRANCH% >> logs\daily_task.log 2>&1
"%PY%" scripts\fetch_eod.py VCB CTD >> logs\daily_task.log 2>&1
"%PY%" scripts\watchlist.py update >> logs\daily_task.log 2>&1
"%PY%" scripts\run_evening.py >> logs\daily_task.log 2>&1
"%PY%" scripts\health_check.py >> logs\daily_task.log 2>&1

git add data dashboard\auto_dashboard.html >> logs\daily_task.log 2>&1
git diff --cached --quiet && goto push
git commit -m "Cap nhat du lieu daily task (tu dong)" >> logs\daily_task.log 2>&1
:push
git pull --rebase origin %BRANCH% >> logs\daily_task.log 2>&1
git push origin %BRANCH% >> logs\daily_task.log 2>&1

echo ==== XONG %time% ==== >> logs\daily_task.log
