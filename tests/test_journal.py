"""Nhật ký giao dịch — cuốn sổ không được sập vì một dòng hỏng.

`docs/AUDIT_REPORT.md` mục L8 ghi nhận nguy cơ chia cho 0 từ đợt audit đầu và
đánh dấu "chưa xảy ra trong thực tế nhưng cần guard". Guard đó chưa từng được
thêm; tái hiện được bằng đúng hai lệnh:

    journal.py add BUY VCB 58.5 0
    journal.py report      → ZeroDivisionError, mất toàn bộ báo cáo

Sửa ở HAI tầng, cố ý: chặn ở cửa vào (`cmd_add`) để dòng hỏng không vào được
file, và guard ở chỗ đọc (`cmd_report`) cho những dòng đã lỡ ghi trước đây —
tầng thứ hai mới là tầng cứu được cuốn sổ đang có sẵn dòng hỏng.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JOURNAL_PY = ROOT / "scripts" / "journal.py"


def _report_with(tmp_path, rows):
    """Chạy cmd_report trên một file nhật ký riêng, không đụng dữ liệu thật."""
    path = tmp_path / "journal.jsonl"
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                    encoding="utf-8")
    code = (
        "import sys, pathlib;"
        f"sys.path.insert(0, {str(ROOT)!r}); sys.path.insert(0, {str(ROOT / 'scripts')!r});"
        "import journal;"
        f"journal.JOURNAL = pathlib.Path({str(path)!r});"
        "journal.cmd_report()"
    )
    return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)


def _add(tmp_path, *args):
    path = tmp_path / "journal.jsonl"
    code = (
        "import sys, pathlib;"
        f"sys.path.insert(0, {str(ROOT)!r}); sys.path.insert(0, {str(ROOT / 'scripts')!r});"
        "import journal;"
        f"journal.JOURNAL = pathlib.Path({str(path)!r});"
        f"journal.cmd_add({list(args)!r})"
    )
    return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)


# --- L8: chia cho 0 ---------------------------------------------------------

def test_dong_qty_0_khong_lam_sap_bao_cao(tmp_path):
    r = _report_with(tmp_path, [
        {"date": "2026-08-20", "side": "BUY", "ticker": "VCB",
         "price": 58.5, "qty": 0, "note": "", "rec": ""},
    ])
    assert r.returncode == 0, r.stderr
    assert "ZeroDivisionError" not in r.stderr
    assert "dòng nhật ký hỏng" in r.stdout


def test_khoi_luong_0_bi_chan_ngay_o_cua_vao(tmp_path):
    r = _add(tmp_path, "BUY", "VCB", "58.5", "0")
    assert r.returncode != 0
    assert "Khối lượng phải > 0" in (r.stderr + r.stdout)
    assert not (tmp_path / "journal.jsonl").exists()


def test_gia_am_bi_chan(tmp_path):
    r = _add(tmp_path, "BUY", "VCB", "-58.5", "1000")
    assert r.returncode != 0 and "Giá phải > 0" in (r.stderr + r.stdout)


def test_gia_khong_phai_so_bi_chan_co_huong_dan(tmp_path):
    r = _add(tmp_path, "BUY", "VCB", "nam muoi", "1000")
    assert r.returncode != 0 and "phải là số" in (r.stderr + r.stdout)


def test_lenh_hop_le_van_ghi_binh_thuong(tmp_path):
    r = _add(tmp_path, "BUY", "VCB", "58.5", "1000")
    assert r.returncode == 0
    rows = [json.loads(l) for l in
            (tmp_path / "journal.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    assert rows[0]["price"] == 58.5 and rows[0]["qty"] == 1000


# --- L7: đối chiếu khuyến nghị ---------------------------------------------

def test_mua_nguoc_khuyen_nghi_bi_bat_trong_bao_cao(tmp_path):
    r = _report_with(tmp_path, [
        {"date": "2026-08-20", "side": "BUY", "ticker": "CTD",
         "price": 62.4, "qty": 1000, "note": "", "rec": "ĐỨNG NGOÀI"},
    ])
    assert r.returncode == 0, r.stderr
    assert "ĐI NGƯỢC" in r.stdout and "ĐỨNG NGOÀI" in r.stdout


def test_ban_sau_KHONG_MUA_THEM_khong_bi_bat_oan(tmp_path):
    r = _report_with(tmp_path, [
        {"date": "2026-08-20", "side": "BUY", "ticker": "CTD",
         "price": 62.4, "qty": 1000, "note": "", "rec": "MUA THĂM DÒ"},
        {"date": "2026-08-21", "side": "SELL", "ticker": "CTD",
         "price": 63.0, "qty": 1000, "note": "", "rec": "KHÔNG MUA THÊM"},
    ])
    assert r.returncode == 0, r.stderr
    assert "ĐI NGƯỢC" not in r.stdout


def test_giao_dich_khi_CHUA_DU_DU_LIEU_duoc_tach_rieng(tmp_path):
    r = _report_with(tmp_path, [
        {"date": "2026-08-25", "side": "BUY", "ticker": "VCB", "price": 60.3,
         "qty": 100, "note": "", "rec": "CHƯA ĐỦ DỮ LIỆU ĐỂ RA QUYẾT ĐỊNH"},
    ])
    assert r.returncode == 0, r.stderr
    assert "CHƯA RA ĐƯỢC khuyến nghị" in r.stdout
    assert "ĐI NGƯỢC" not in r.stdout


def test_rec_khong_doc_duoc_duoc_bao_chu_khong_im_lang(tmp_path):
    r = _report_with(tmp_path, [
        {"date": "2026-08-25", "side": "BUY", "ticker": "VCB", "price": 60.3,
         "qty": 100, "note": "", "rec": "thấy rẻ thì mua"},
    ])
    assert r.returncode == 0, r.stderr
    assert "KHÔNG ĐỌC ĐƯỢC" in r.stdout


# --- Không phá phần đang chạy đúng -----------------------------------------

def test_lai_lo_FIFO_van_dung(tmp_path):
    r = _report_with(tmp_path, [
        {"date": "2026-08-01", "side": "BUY", "ticker": "VCB",
         "price": 58.0, "qty": 1000, "note": "", "rec": ""},
        {"date": "2026-08-20", "side": "SELL", "ticker": "VCB",
         "price": 60.0, "qty": 1000, "note": "", "rec": ""},
    ])
    assert r.returncode == 0, r.stderr
    assert "2,000,000" in r.stdout  # (60,0 − 58,0) nghìn × 1000 cp
