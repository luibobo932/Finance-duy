"""Data contract chung cho mọi số liệu tài chính trong Finance-duy.

Mọi số liệu đi vào hệ thống (giá vàng, giá cổ phiếu, lãi suất, tỷ giá...) nên
được bọc trong một DataPoint thay vì là số trần trụi, để biết: số này từ đâu,
lúc nào, tin cậy đến đâu, có phải hàng dự phòng không.
"""
from .schema import Confidence, DataPoint, SourceStatus

__all__ = ["DataPoint", "SourceStatus", "Confidence"]
