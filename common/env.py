"""Nạp biến môi trường từ file .env (KHÔNG commit vào git — xem .gitignore).

Không dùng thư viện ngoài (python-dotenv) cho một nhu cầu đơn giản — parser
tối giản, đủ dùng cho KEY=VALUE mỗi dòng.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"


def load_env(path: Path | None = None) -> dict[str, str]:
    """Đọc .env, TRẢ VỀ dict (không tự ý ghi đè os.environ đã có sẵn)."""
    path = path or ENV_PATH
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        values[key.strip()] = val.strip()
    return values


def get_env(key: str, default: str | None = None) -> str | None:
    """Ưu tiên biến môi trường thật (os.environ) trước, .env sau."""
    if key in os.environ:
        return os.environ[key]
    return load_env().get(key, default)
