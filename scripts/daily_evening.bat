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
rem Health check voi --alert: gui Telegram khi FAIL (chong spam: chi gui khi
rem VUA chuyen sang FAIL hoac da 3 ngay ke tu lan nhac truoc).
rem QUAN TRONG: phai kiem tra errorlevel NGAY SAU lenh nay. Truoc 13/8 khong
rem ai doc ket qua health check, va WARN khong bao gio leo thang thanh FAIL -
rem do la co che khien automation ket 7 ngay (20-26/7) van "thanh cong" moi
rem lan chay va khong ai biet.
rem Bao cao KE HOACH (suc mua sau lam phat + muc tieu 10 ty) - gui THU HAI
rem hang tuan. Khong gui hang ngay: noi dung chi doi khi gia tai san doi hoac
rem khi chu danh muc sua config/plan.yaml, gui moi ngay se thanh nhieu va bi
rem bo qua - dung cai benh "canh bao lap mai" da sua o alert_health.py.
for /f %%d in ('powershell -NoProfile -Command "(Get-Date).DayOfWeek.value__"') do set DOW=%%d
if "%DOW%"=="1" (
    "%PY%" scripts\send_report.py plan >> logs\daily_task.log 2>&1
    if errorlevel 1 echo [CANH BAO] Khong gui duoc bao cao ke hoach. >> logs\daily_task.log
)

"%PY%" scripts\health_check.py --alert >> logs\daily_task.log 2>&1
if errorlevel 1 (
    echo [LOI] HEALTH CHECK FAIL - du lieu qua cu hoac co van de an ninh. >> logs\daily_task.log
    echo Da gui canh bao Telegram neu da cau hinh. Xem chi tiet o tren. >> logs\daily_task.log
)

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
