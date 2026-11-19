"""Pydantic-модели запросов обёртки."""

from pydantic import BaseModel, Field, field_validator


class CreateCampaignRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    geo: str = Field(min_length=2, max_length=2, description="Код страны, например AU")
    offer_id: int = Field(gt=0)
    domain_id: int | None = None

    @field_validator("geo")
    @classmethod
    def geo_upper(cls, v: str) -> str:
        v = v.strip().upper()
        if not v.isalpha() or len(v) != 2:
            raise ValueError("гео-код — две латинские буквы, например AU")
        return v


class OfferRequest(BaseModel):
    offer_id: int = Field(gt=0)
