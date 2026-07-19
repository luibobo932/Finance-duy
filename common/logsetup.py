"""Structured logging cho các script Finance-duy.

Thiết kế quan trọng: đây là log CHẨN ĐOÁN (cảnh báo chất lượng dữ liệu, lỗi
nguồn...), KHÔNG thay thế phần in ra màn hình của các báo cáo (bản tin xu
hướng, tài sản ròng...) — những phần đó vẫn dùng print() vì đó chính là sản
phẩm mà routine/người dùng đọc trực tiếp từ stdout. Logger ở đây ghi ra file
JSON Lines trong logs/ và chỉ đẩy WARNING trở lên ra stderr (không phải
stdout) để không lẫn vào nội dung báo cáo.
"""
from __future__ import annotations

import json
import logging
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = ROOT / "logs"


def new_run_id() -> str:
    return uuid.uuid4().hex[:12]


class _JsonLineFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "run_id": getattr(record, "run_id", None),
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        extra = getattr(record, "extra_fields", None)
        if extra:
            payload.update(extra)
        return json.dumps(payload, ensure_ascii=False)


class _RunIdFilter(logging.Filter):
    def __init__(self, run_id: str):
        super().__init__()
        self.run_id = run_id

    def filter(self, record: logging.LogRecord) -> bool:
        record.run_id = self.run_id
        return True


def get_logger(name: str, run_id: str | None = None, console_level: int = logging.WARNING) -> logging.Logger:
    """Tạo logger ghi JSON Lines vào logs/<run_id>.jsonl + cảnh báo ra stderr.

    An toàn khi gọi nhiều lần với cùng `name` (không nhân đôi handler).
    """
    run_id = run_id or new_run_id()
    logger = logging.getLogger(f"finance_duy.{name}")
    logger.setLevel(logging.DEBUG)
    logger.addFilter(_RunIdFilter(run_id))

    if getattr(logger, "_finance_duy_configured", False):
        return logger

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(LOG_DIR / f"{run_id}.jsonl", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(_JsonLineFormatter())
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(stream=sys.stderr)
    console_handler.setLevel(console_level)
    console_handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(console_handler)

    logger.propagate = False
    logger._finance_duy_configured = True  # type: ignore[attr-defined]
    return logger
