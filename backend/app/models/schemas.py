from pydantic import BaseModel, Field


class HealthStatusResponse(BaseModel):
    """Schema for the health-check status response."""

    status: str = Field(..., examples=["running"], description="Service operational status.")
    items_loaded: int = Field(
        ...,
        ge=0,
        examples=[5],
        description="Total count of target items currently loaded in memory.",
    )
