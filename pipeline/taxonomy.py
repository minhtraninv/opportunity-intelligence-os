#!/usr/bin/env python3
"""Canonical procurement taxonomy for Opportunity Intelligence OS.

Rules intentionally prefer specific commercial forms over generic words. The module
returns a primary category plus all matched tags so the taxonomy can evolve without
leaving old history permanently misclassified.
"""
from __future__ import annotations

import re

RULES = (
    ("office_goods", (
        "văn phòng phẩm", "máy tính", "máy in", "mực in", "thiết bị văn phòng",
        "bàn ghế", "máy photocopy", "laptop", "máy chủ", "server",
    )),
    ("digital_services", (
        "phần mềm", "website", "hệ thống thông tin", "chuyển đổi số", "số hóa",
        "số hoá", "gis", "dịch vụ công nghệ thông tin", "cơ sở dữ liệu", "dữ liệu số",
        "pacs", "his", "lis", "emr", "bản quyền phần mềm",
    )),
    ("consulting", (
        "tư vấn", "khảo sát", "giám sát", "thẩm tra", "lập hồ sơ", "quản lý dự án",
        "lập báo cáo", "thẩm định", "quy hoạch", "đánh giá tác động",
    )),
    ("printing_media", (
        "in ấn", "in tài liệu", "in báo", "ấn phẩm", "thiết kế ấn phẩm",
        "thiết kế đồ họa", "truyền thông", "quảng cáo", "pano", "poster",
    )),
    ("maintenance", (
        "bảo trì", "bảo dưỡng", "sửa chữa", "vệ sinh", "kiểm định", "facility",
    )),
    ("garment_ppe", (
        "đồng phục", "bảo hộ lao động", "ppe", "quần áo bảo hộ", "giày bảo hộ",
    )),
    ("food_services", (
        "suất ăn", "thực phẩm", "catering", "nước uống", "bếp ăn", "bán trú",
    )),
    ("logistics", (
        "thuê xe", "vận chuyển", "vận tải", "logistics", "giao nhận", "kho bãi",
    )),
    ("medical", (
        "thuốc", "vật tư y tế", "thiết bị y tế", "xét nghiệm", "dược", "hóa chất y tế",
    )),
    ("machinery", (
        "máy móc", "phụ tùng", "thiết bị công nghiệp", "dây chuyền", "máy nén",
    )),
    ("construction", (
        "thi công", "xây dựng", "xây lắp", "công trình", "cầu đường", "hạ tầng kỹ thuật",
    )),
)


def normalize(text) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip().casefold()


def matched_categories(title: str) -> list[str]:
    text = normalize(title)
    matches = []
    for category, phrases in RULES:
        if any(phrase.casefold() in text for phrase in phrases):
            matches.append(category)
    return matches or ["other"]


def classify(title: str) -> str:
    return matched_categories(title)[0]
