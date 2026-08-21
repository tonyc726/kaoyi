from __future__ import annotations

import re

from adapters.base import get_html, stub, today
from kaoyi.models import Plan, PriceCell, Snapshot, Vendor

SOURCE_URL = "https://help.aliyun.com/zh/model-studio/coding-plan"
VENDOR_ID = "aliyun"

VENDOR = Vendor(
    id=VENDOR_ID,
    name="阿里·百炼",
    name_en="Alibaba Model Studio",
    kind="plan",
    status="LIMITED",
    region="CN",
    currency="CNY",
    official_url=SOURCE_URL,
    buy_url=SOURCE_URL,
    docs_url=SOURCE_URL,
    adapter="aliyun",
    short="Coding Plan",
    notes="",
)


def fetch() -> Snapshot:
    fetched, html = get_html(SOURCE_URL)
    if not fetched:
        return stub(VENDOR, notes=f"Fetch failed. Source {SOURCE_URL}")

    match = re.search(r"¥\s*200\s*/\s*月", html)
    if not match:
        return stub(VENDOR, fetched_ok=True, notes="¥200/月 not found. No invented number.")

    as_of = today()
    pro = Plan(
        id="pro",
        name="Pro",
        price=PriceCell(
            display="¥200",
            amount=200,
            currency="CNY",
            period="month",
            source_url=SOURCE_URL,
            as_of=as_of,
            note="官网目录价",
        ),
        quota="每 5 小时 6,000 次；每周 45,000 次；每月 90,000 次"
        if "6,000" in html or "6000" in html
        else "-",
    )
    lite = Plan(
        id="lite",
        name="Lite",
        status="SOLD OUT",
        price=PriceCell(
            display="-",
            amount=None,
            currency="CNY",
            period="month",
            source_url=SOURCE_URL,
            as_of=as_of,
            note="已停新购",
        ),
        quota="已停新购 / 停续费",
    )
    return Snapshot(
        vendor_id=VENDOR_ID,
        source_url=SOURCE_URL,
        as_of=as_of,
        fetched_ok=True,
        parse_ok=True,
        status="LIMITED",
        billing_unit="月订阅 · 请求次数",
        notes="Parsed Pro list price from official help. Lite has no current list price.",
        plans=[lite, pro],
    )
