from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Kind = Literal["plan", "usage"]
Layer = Literal["official", "community", "editorial"]
Status = Literal["OPEN", "LIMITED", "SOLD OUT", "PAUSED"]


class RadarAxis(BaseModel):
    id: str
    label: str
    invert: bool = False


class SiteConfig(BaseModel):
    site_name: str
    site_name_en: str
    one_liner: str
    site_base: str
    pages_url: str
    usd_to_cny_rate: float
    usd_to_cny_as_of: str
    usd_to_cny_note: str
    build_as_of: str
    footer_zh: str
    footer_en: str
    layers: list[dict[str, str]]
    radar_axes: list[RadarAxis]
    status_literals: list[str]


class Vendor(BaseModel):
    id: str
    name: str
    name_en: str
    kind: Kind
    status: Status
    region: str
    currency: str
    official_url: str
    buy_url: str
    docs_url: str
    adapter: str
    short: str
    notes: str = ""


class PriceCell(BaseModel):
    display: str = "-"
    amount: float | None = None
    currency: str | None = None
    period: str | None = None
    source_url: str
    as_of: str
    note: str | None = None

    @property
    def is_missing(self) -> bool:
        return self.display.strip() in {"", "-"}


class Plan(BaseModel):
    id: str
    name: str
    price: PriceCell
    quota: str = "-"
    notes: str = ""
    status: str | None = None

    def display_status(self, vendor_status: str) -> str:
        return self.status or vendor_status


class UsageMeta(BaseModel):
    platform_fee: str = "-"
    min_spend: str = "-"
    token_list_price: str = "-"
    source_url: str
    as_of: str


class Snapshot(BaseModel):
    vendor_id: str
    source_url: str
    as_of: str
    fetched_ok: bool = False
    parse_ok: bool = False
    status: str = "OPEN"
    billing_unit: str = "-"
    notes: str = ""
    plans: list[Plan] = Field(default_factory=list)
    usage: UsageMeta | None = None


class Review(BaseModel):
    status: str = "未评"
    scores: dict[str, int] = Field(default_factory=dict)
    note: str = ""

    @property
    def is_placeholder(self) -> bool:
        return self.status == "未评" or not self.scores


class Event(BaseModel):
    id: str
    vendor_id: str
    layer: Layer
    kind: str
    title: str
    summary: str
    as_of: str
    source_url: str = ""
    example: bool = False
    status: str = "OPEN"
    note: str = ""
    # Omitted in YAML: official price_change/promo default high;
    # example / community anecdote default low.
    confidence: float | None = Field(default=None, ge=0, le=1)

    @property
    def effective_confidence(self) -> float:
        if self.confidence is not None:
            return self.confidence
        if self.example or self.layer == "community" or self.kind in {"example", "anecdote"}:
            return 0.3
        if self.layer == "official" and self.kind in {"price_change", "promo"}:
            return 0.9
        return 0.5

    @property
    def is_unconfirmed(self) -> bool:
        return self.example or self.effective_confidence < 0.6


class FetchStatus(BaseModel):
    """Sidecar for today's adapter fetch/parse failures, not snapshot parse_ok."""

    as_of: str
    failed_vendor_ids: list[str] = Field(default_factory=list)

    @property
    def failed_count(self) -> int:
        return len(self.failed_vendor_ids)


class ReviewsFile(BaseModel):
    axes: list[str]
    vendors: dict[str, Review]


class VendorPage(BaseModel):
    vendor: Vendor
    snapshot: Snapshot
    review: Review
    events: list[Event]
    radar_svg: str


class SiteData(BaseModel):
    config: SiteConfig
    vendors: list[Vendor]
    snapshots: dict[str, Snapshot]
    reviews: ReviewsFile
    events: list[Event]
    fetch_status: FetchStatus | None = None
    pages: list[VendorPage] = Field(default_factory=list)

    def vendor(self, vendor_id: str) -> Vendor:
        for item in self.vendors:
            if item.id == vendor_id:
                return item
        raise KeyError(vendor_id)

    def page(self, vendor_id: str) -> VendorPage:
        for item in self.pages:
            if item.vendor.id == vendor_id:
                return item
        raise KeyError(vendor_id)

    def plan_vendors(self) -> list[VendorPage]:
        return [page for page in self.pages if page.vendor.kind == "plan"]

    def usage_vendors(self) -> list[VendorPage]:
        return [page for page in self.pages if page.vendor.kind == "usage"]

    def events_for(self, vendor_id: str) -> list[Event]:
        return [event for event in self.events if event.vendor_id == vendor_id]


def empty_price(source_url: str, as_of: str, note: str | None = None) -> PriceCell:
    return PriceCell(
        display="-",
        amount=None,
        currency=None,
        period=None,
        source_url=source_url,
        as_of=as_of,
        note=note,
    )


def empty_snapshot(vendor: Vendor, as_of: str) -> Snapshot:
    return Snapshot(
        vendor_id=vendor.id,
        source_url=vendor.official_url,
        as_of=as_of,
        fetched_ok=False,
        parse_ok=False,
        status=vendor.status,
        billing_unit="-",
        notes="Adapter stub. No invented numbers.",
        plans=[],
    )


def model_json(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json")
