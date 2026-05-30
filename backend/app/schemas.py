"""
Pydantic models for the Prospect Research API.

- EnrichRequest: validates incoming POST /enrich body.
- CompanyProfile: enforces the strict output schema for all API responses.
"""

from typing import List
from pydantic import BaseModel, field_validator, model_validator


class EnrichRequest(BaseModel):
    """
    Request body for POST /enrich.

    website_name is optional — callers may supply a human-readable label
    (e.g. "Zoho") to override the URL-derived name in the saved profile.
    url is required and must look like a valid HTTP/HTTPS address.
    """

    website_name: str = ""
    url: str

    @field_validator("url")
    @classmethod
    def url_must_not_be_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("url cannot be empty.")
        return v

    @model_validator(mode="after")
    def url_must_look_like_website(self) -> "EnrichRequest":
        url = self.url.strip().lower()
        # Accept bare domains too (we normalize in the enrichment layer)
        if not (
            url.startswith("http://")
            or url.startswith("https://")
            or "." in url
        ):
            raise ValueError(
                "url does not look like a valid website URL. "
                "Example: https://www.zoho.com"
            )
        return self


class CompanyProfile(BaseModel):
    """
    Strict output schema.  Every field must be present; no extras allowed.
    """

    website_name: str = ""
    company_name: str = ""
    address: str = ""
    mobile_number: str = ""
    mail: List[str] = []
    core_service: str = ""
    target_customer: str = ""
    probable_pain_point: str = ""
    outreach_opener: str = ""

    model_config = {"extra": "ignore"}
