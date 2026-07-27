@echo off
rem Ban tin chieu tu dong - chay boi Windows Task Scheduler 18:41 hang ngay.
rem Luong: dong bo sach voi origin -> tai EOD that -> cap nhat watchlist
rem -> ban tin chieu (tu gui Telegram) -> health check -> commit + push.
rem LUU Y: file nay phai giu ASCII thuan tuy - cmd parse loi voi UTF-8 tieng Viet.
rem Duong dan repo lay tu vi tri file bat (%~dp0 = ...\Finance-duy\scripts\).
rem
rem QUAN TRONG (phat hien 2026-07-27): co mot routine cloud claude.ai KHAC
rem chay sang/chieu tren cung nhanh git, cung ghi vao data/watchlist.json va
rem data/history.jsonl. "git pull --rebase" tung bi conflict va KET LAI GIUA
rem CHUNG nhieu ngay lien tuc ma khong ai biet, khien du lieu khong dong bo.
rem Chien luoc moi: LUON reset --hard ve origin truoc khi lam gi (bo qua moi
rem sai lech local con sot - fetch_eod/watchlist deu idempotent, du lieu gia
rem thuc te tu API van tai lai duoc lan sau), roi push THANG (khong rebase).
rem Neu push that bai vi remote vua doi (writer khac vua push), KHONG tu
rem dong merge/rebase - chi log canh bao va thoat, tranh lap lai tinh trang
rem ket rebase. Lan chay ke tiep se tu dong bo lai vi buoc dau la reset cung.

cd /d "%~dp0.."
set PYTHONIOENCODING=utf-8
set PY=C:\Users\Duy\AppData\Local\Programs\Python\Python312\python.exe
set BRANCH=claude/investment-news-aggregator-w81l70

echo ==== DAILY TASK %date% %time% ==== >> logs\daily_task.log

git fetch origin %BRANCH% >> logs\daily_task.log 2>&1
git reset --hard origin/%BRANCH% >> logs\daily_task.log 2>&1

"%PY%" scripts\fetch_eod.py VCB CTD >> logs\daily_task.log 2>&1
"%PY%" scripts\fetch_market_snapshot.py chieu >> logs\daily_task.log 2>&1
"%PY%" scripts\watchlist.py update >> logs\daily_task.log 2>&1
"%PY%" scripts\run_evening.py >> logs\daily_task.log 2>&1
"%PY%" scripts\health_check.py >> logs\daily_task.log 2>&1

git add data dashboard\auto_dashboard.html >> logs\daily_task.log 2>&1
git diff --cached --quiet && goto nochange
git commit -m "Cap nhat du lieu daily task (tu dong)" >> logs\daily_task.log 2>&1
git push origin %BRANCH% >> logs\daily_task.log 2>&1
if errorlevel 1 (
    echo [CANH BAO] Push that bai - remote co the vua doi. Khong tu rebase. >> logs\daily_task.log
    echo Du lieu van con local, lan chay ke tiep se tu dong bo lai. >> logs\daily_task.log
)
goto end
:nochange
echo Khong co thay doi de commit. >> logs\daily_task.log
:end

echo ==== XONG %time% ==== >> logs\daily_task.log
