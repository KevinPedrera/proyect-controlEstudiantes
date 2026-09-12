"""Contratos HTTP de departamentos."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Availability = Literal["DISPONIBLE", "NO_DISPONIBLE"]


class ActiveCounts(BaseModel):
    model_config = ConfigDict(extra='forbid')
    en_camino: int = Field(ge=0, strict=True)
    en_atencion: int = Field(ge=0, strict=True)


class AvailabilityUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    availability: Availability
    confirmed_active_counts: ActiveCounts | None = None


class DepartmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    group: Literal["INSPECCION", "DECE", "SALUD"]
    active: bool
    availability: Availability
