from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

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


class OfficialChannel(BaseModel):
    """Social/media account linked from that vendor's own official domain."""

    kind: str
    url: str
    handle: str = ""
    label: str = ""
    note: str = ""

    @property
    def display_label(self) -> str:
        if self.label.strip():
            return self.label.strip()
        kind_labels = {
            "x": "X",
            "youtube": "YouTube",
            "linkedin": "LinkedIn",
            "discord": "Discord",
            "github": "GitHub",
            "instagram": "Instagram",
            "wechat": "微信",
        }
        base = kind_labels.get(self.kind, self.kind)
        handle = self.handle.strip().lstrip("@")
        if self.kind == "x" and handle:
            return f"X @{handle}"
        return base


SOURCE_KIND_LABELS = {
    "blog": "BLOG",
    "releases": "RELEASES",
    "status": "STATUS",
    "forum": "FORUM",
}


class OfficialPost(BaseModel):
    title: str
    date: str = ""
    source_url: str
    as_of: str
    source_kind: str = "blog"

    @property
    def source_label(self) -> str:
        return SOURCE_KIND_LABELS.get(self.source_kind, "BLOG")


class OfficialPostsFile(BaseModel):
    vendor_id: str
    source_url: str
    as_of: str
    fetched_ok: bool = False
    parse_ok: bool = False
    posts: list[OfficialPost] = Field(default_factory=list)


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
    channels: list[OfficialChannel] = Field(default_factory=list)


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
    reasons: dict[str, str] = Field(default_factory=dict)
    note: str = ""
    updated_at: str = ""

    @property
    def is_placeholder(self) -> bool:
        return self.status == "未评" or not self.scores

    @field_validator("scores")
    @classmethod
    def scores_are_integers_1_to_5(cls, value: dict[str, int]) -> dict[str, int]:
        for axis, score in value.items():
            if isinstance(score, bool) or not isinstance(score, int) or not (1 <= score <= 5):
                raise ValueError(f"{axis} score must be an integer 1–5")
        return value

    @model_validator(mode="after")
    def reasons_for_scored_axes(self) -> Review:
        if self.scores and self.status == "未评":
            raise ValueError("a scored review cannot stay 未评")
        for axis in self.scores:
            reason = (self.reasons.get(axis) or "").strip()
            if not reason:
                raise ValueError(f"{axis} needs a one-line reason")
        return self


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
    source_kind: str | None = None
    # Omitted in YAML: official price_change/promo default high;
    # example / community anecdote default low.
    confidence: float | None = Field(default=None, ge=0, le=1)

    @property
    def source_label(self) -> str:
        if self.source_kind in SOURCE_KIND_LABELS:
            return SOURCE_KIND_LABELS[self.source_kind]
        return "OFFICIAL"

    @property
    def effective_confidence(self) -> float:
        if self.confidence is not None:
            return self.confidence
        if self.example or self.layer == "community" or self.kind in {"example", "anecdote"}:
            return 0.3
        if self.layer == "official" and self.kind in {
            "price_change",
            "promo",
            "official_announce",
            "status",
        }:
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

    @model_validator(mode="after")
    def scores_use_declared_axes(self) -> ReviewsFile:
        allowed = set(self.axes)
        for vendor_id, review in self.vendors.items():
            unknown = set(review.scores) - allowed
            if unknown:
                raise ValueError(f"{vendor_id} has unknown axes: {sorted(unknown)}")
        return self


class VendorPage(BaseModel):
    vendor: Vendor
    snapshot: Snapshot
    review: Review
    events: list[Event]
    radar_svg: str
    official_posts: list[OfficialPost] = Field(default_factory=list)


class SiteData(BaseModel):
    config: SiteConfig
    vendors: list[Vendor]
    snapshots: dict[str, Snapshot]
    reviews: ReviewsFile
    events: list[Event]
    fetch_status: FetchStatus | None = None
    official_posts: dict[str, OfficialPostsFile] = Field(default_factory=dict)
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
