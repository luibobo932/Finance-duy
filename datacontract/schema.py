"""Schema chuẩn cho một số liệu tài chính: DataPoint.

Mọi trường số (giá, tỷ giá, lãi suất...) khi đi qua hệ thống nên được bọc
trong DataPoint thay vì truyền số thô, để Risk Officer / Decision Engine
(Phase 7) biết được nên tin số này đến đâu.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class SourceStatus(str, Enum):
    """Trạng thái sức khỏe của một nguồn/số liệu."""

    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    STALE = "STALE"
    FAILED = "FAILED"
    CONFLICTING = "CONFLICTING"


class Confidence(str, Enum):
    """Độ tin cậy chủ quan gắn với nguồn dữ liệu.

    HIGH   = API chính thức / ảnh chụp thực tế do người dùng cung cấp
    MEDIUM = báo chí uy tín, tổng hợp qua tìm kiếm, có trích dẫn nguồn rõ ràng
    LOW    = suy luận/ước tính/ngoại suy, hoặc nguồn không xác định được độ mới
    """

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class DataPoint:
    """Một số liệu tài chính kèm đầy đủ ngữ cảnh nguồn gốc.

    Nguyên tắc: nếu `value is None`, đó là "chưa có dữ liệu" — KHÔNG được
    coi là 0 ở bất kỳ tầng tính toán nào phía trên.
    """

    name: str
    value: Optional[float]
    unit: str
    source: str
    source_url: Optional[str] = None
    as_of: Optional[str] = None
    fetched_at: str = field(default_factory=now_iso)
    freshness_seconds: Optional[float] = None
    confidence: str = Confidence.MEDIUM.value
    fallback_used: bool = False
    status: str = SourceStatus.HEALTHY.value
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "source": self.source,
            "source_url": self.source_url,
            "as_of": self.as_of,
            "fetched_at": self.fetched_at,
            "freshness_seconds": self.freshness_seconds,
            "confidence": self.confidence,
            "fallback_used": self.fallback_used,
            "status": self.status,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "DataPoint":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    @property
    def is_missing(self) -> bool:
        return self.value is None
