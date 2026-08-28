from __future__ import annotations

from kaoyi.models import OfficialQuota, Plan, PriceCell, Snapshot, Vendor
from kaoyi.quota import (
    build_unit_cost_leagues,
    hydrate_plan_quota,
    monthly_list_cny,
    parse_official_quota,
)

AS_OF = "2026-08-21"
ZHIPU_DOCS = "https://docs.bigmodel.cn/cn/coding-plan/overview"
ALIYUN_HELP = "https://help.aliyun.com/zh/model-studio/coding-plan"


def _vendor(vendor_id: str, name: str, currency: str = "CNY") -> Vendor:
    return Vendor(
        id=vendor_id,
        name=name,
        name_en=name,
        kind="plan",
        status="OPEN",
        region="CN" if currency == "CNY" else "GLOBAL",
        currency=currency,
        official_url="https://example.com",
        buy_url="https://example.com",
        docs_url="https://example.com",
        adapter=vendor_id,
        short=name,
    )


def _price(
    display: str,
    amount: float | None,
    *,
    currency: str = "CNY",
    source: str = "https://example.com",
) -> PriceCell:
    return PriceCell(
        display=display,
        amount=amount,
        currency=currency,
        period="month",
        source_url=source,
        as_of=AS_OF,
    )


def _plan(
    sku_id: str,
    name: str,
    price: PriceCell,
    quota: str = "-",
    official_quota: OfficialQuota | None = None,
) -> Plan:
    return Plan(
        id=sku_id,
        name=name,
        price=price,
        quota=quota,
        official_quota=official_quota,
    )


def _snapshot(vendor_id: str, plans: list[Plan]) -> Snapshot:
    return Snapshot(
        vendor_id=vendor_id,
        source_url="https://example.com",
        as_of=AS_OF,
        fetched_ok=True,
        parse_ok=True,
        status="OPEN",
        plans=plans,
    )


def test_parse_weekly_credits_and_monthly_requests() -> None:
    weekly = parse_official_quota(
        "每周 10,000 积分；5 小时 2,000 积分（文档）",
        ZHIPU_DOCS,
        AS_OF,
    )
    assert weekly is not None
    assert weekly.amount == 10000
    assert weekly.unit == "credits"
    assert weekly.window == "week"

    monthly = parse_official_quota(
        "每 5 小时 6,000 次；每周 45,000 次；每月 90,000 次",
        ALIYUN_HELP,
        AS_OF,
    )
    assert monthly is not None
    assert monthly.amount == 90000
    assert monthly.unit == "requests"
    assert monthly.window == "month"


def test_fuzzy_agent_and_multiplier_are_not_quotas() -> None:
    fuzzy = "5 小时固定窗口和周窗口；约 3–4 个 Agent"
    assert parse_official_quota(fuzzy, "https://x", AS_OF) is None
    assert parse_official_quota("-", "https://x", AS_OF) is None
    assert parse_official_quota("更高用量；Maximum Codex tasks", "https://x", AS_OF) is None
    assert parse_official_quota("Limited Agent requests；Composer", "https://x", AS_OF) is None


def test_hydrate_reads_official_quota_string_without_inventing() -> None:
    plan = _plan(
        "lite",
        "Lite",
        _price("¥118", 118, source="https://www.bigmodel.cn/glm-coding"),
        quota="每周 10,000 积分；5 小时 2,000 积分（文档）",
    )
    hydrated = hydrate_plan_quota(plan, source_url=ZHIPU_DOCS, as_of=AS_OF)
    assert hydrated.official_quota is not None
    assert hydrated.official_quota.amount == 10000
    assert hydrated.quota == plan.quota


def test_missing_price_or_quota_stays_unranked() -> None:
    vendors = [_vendor("demo", "Demo")]
    snapshots = {
        "demo": _snapshot(
            "demo",
            [
                _plan("no-price", "NoPrice", _price("-", None), quota="每周 10,000 积分"),
                _plan("no-quota", "NoQuota", _price("¥100", 100), quota="-"),
            ],
        )
    }
    leagues, unranked = build_unit_cost_leagues(vendors, snapshots, 6.8)
    assert leagues == []
    reasons = {row.sku_id: row.reason for row in unranked}
    assert "可核对刊例" in reasons["no-price"]
    assert "可核对用量" in reasons["no-quota"]


def test_different_quota_units_never_share_a_league() -> None:
    zhipu = _vendor("zhipu", "智谱AI")
    aliyun = _vendor("aliyun", "阿里·百炼")
    snapshots = {
        "zhipu": _snapshot(
            "zhipu",
            [
                _plan(
                    "lite",
                    "Lite",
                    _price("¥118", 118),
                    quota="每周 10,000 积分",
                    official_quota=OfficialQuota(
                        amount=10000,
                        unit="credits",
                        window="week",
                        source_url=ZHIPU_DOCS,
                        as_of=AS_OF,
                    ),
                )
            ],
        ),
        "aliyun": _snapshot(
            "aliyun",
            [
                _plan(
                    "pro",
                    "Pro",
                    _price("¥200", 200),
                    quota="每月 90,000 次",
                    official_quota=OfficialQuota(
                        amount=90000,
                        unit="requests",
                        window="month",
                        source_url=ALIYUN_HELP,
                        as_of=AS_OF,
                    ),
                )
            ],
        ),
    }
    leagues, unranked = build_unit_cost_leagues([zhipu, aliyun], snapshots, 6.8)
    assert unranked == []
    assert {league.id for league in leagues} == {"credits/week", "requests/month"}
    by_id = {league.id: league for league in leagues}
    assert [row.sku_id for row in by_id["credits/week"].rows] == ["lite"]
    assert [row.sku_id for row in by_id["requests/month"].rows] == ["pro"]
    assert "本轮最低" in by_id["credits/week"].opinion
    assert "智谱AI Lite" in by_id["credits/week"].opinion


def test_usd_list_price_is_editorial_conversion() -> None:
    monthly, converted = monthly_list_cny(_price("$20", 20, currency="USD"), 6.8)
    assert converted is True
    assert monthly == 20 * 6.8
    missing, flag = monthly_list_cny(_price("-", None), 6.8)
    assert missing is None
    assert flag is False
