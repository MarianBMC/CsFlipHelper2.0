from pydantic import BaseModel, Field


class DealResponse(BaseModel):
    """Schema representing a detected arbitrage deal."""

    listing_id: str = Field(..., description="Unique CSFloat listing ID.")
    market_hash_name: str = Field(..., description="CS2 item market hash name.")
    price: float = Field(..., description="Listing buy price in USD.")
    max_buy_price: float = Field(..., description="Target maximum buy price in USD.")
    net_profit: float = Field(..., description="Estimated net profit in USD after fees.")
    float_value: float | None = Field(default=None, description="Item wear float value.")
    buy_url: str = Field(..., description="Direct URL to the CSFloat listing.")
    detected_at: str = Field(..., description="ISO-8601 UTC timestamp when the deal was detected.")


class TargetItemResponse(BaseModel):
    """Schema representing an active target item configuration."""

    market_hash_name: str = Field(..., description="CS2 item market hash name.")
    max_buy_price: float = Field(..., description="Maximum buy price threshold in USD.")


class HealthStatusResponse(BaseModel):
    """Schema for the system status response."""

    status: str = Field(default="online", examples=["online"], description="Service operational status.")
    active_targets: int = Field(
        ...,
        ge=0,
        examples=[5],
        description="Total count of active target items currently loaded in memory.",
    )
    total_deals: int = Field(
        ...,
        ge=0,
        examples=[3],
        description="Total count of detected deals currently stored in memory.",
    )
    targets: list[TargetItemResponse] = Field(
        default_factory=list,
        description="List of active target items monitored by the sniper.",
    )

