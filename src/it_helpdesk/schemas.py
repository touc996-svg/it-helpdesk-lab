from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Priority = Literal["P1", "P2", "P3", "P4"]
TicketStatus = Literal[
    "new", "in_progress", "waiting_on_user", "resolved", "closed", "cancelled"
]
TicketCategory = Literal[
    "account_access", "hardware", "software", "network", "email", "security", "other"
]


class TicketCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=5, max_length=160)
    description: str = Field(min_length=10, max_length=5000)
    requester_name: str = Field(min_length=2, max_length=100)
    requester_email: str = Field(min_length=6, max_length=254)
    category: TicketCategory = "other"
    priority: Priority = "P3"

    @field_validator("requester_email")
    @classmethod
    def validate_email_shape(cls, value: str) -> str:
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Enter a valid email address.")
        return value.lower()


class TicketUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    status: TicketStatus | None = None
    priority: Priority | None = None
    assigned_to: str | None = Field(default=None, max_length=100)


class CommentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    comment: str = Field(min_length=2, max_length=3000)


class AssetCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    asset_tag: str = Field(min_length=3, max_length=40)
    hostname: str = Field(min_length=2, max_length=100)
    device_type: Literal["laptop", "desktop", "server", "mobile", "printer", "other"]
    operating_system: str = Field(min_length=2, max_length=100)
    assigned_to: str | None = Field(default=None, max_length=100)
    location: str | None = Field(default=None, max_length=120)
    status: Literal["in_service", "in_repair", "retired", "lost"] = "in_service"


class KnowledgeArticleCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    slug: str = Field(min_length=3, max_length=100, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    title: str = Field(min_length=5, max_length=180)
    category: TicketCategory
    symptoms: str = Field(min_length=5, max_length=1500)
    resolution_steps: str = Field(min_length=10, max_length=5000)
    owner: str = Field(min_length=2, max_length=100)
    published: bool = False


class AssetUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    assigned_to: str | None = Field(default=None, max_length=100)
    location: str | None = Field(default=None, max_length=120)
    status: Literal["in_service", "in_repair", "retired", "lost"] | None = None
