"""Contratos HTTP de departamentos."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

Availability = Literal["DISPONIBLE", "NO_DISPONIBLE"]


class AvailabilityUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    availability: Availability


class DepartmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    group: Literal["INSPECCION", "DECE", "SALUD"]
    active: bool
    availability: Availability
