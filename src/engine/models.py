from pydantic import BaseModel, field_validator
from typing import Literal
import re

class DbScenarioRequest(BaseModel):
    db_identifier: str
    scenario: str = "primary_db_failure"

    @field_validator('db_identifier')
    @classmethod
    def validate_db_identifier(cls, v):
        if not v or not v.strip():
            raise ValueError("db_identifier cannot be empty")
        # AWS RDS identifiers: 1-63 chars, alphanumeric and hyphens only, must start with letter
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9-]{0,62}$', v):
            raise ValueError("db_identifier must be valid AWS RDS identifier (start with letter, alphanumeric and hyphens, 1-63 chars)")
        return v.strip()

    @field_validator('scenario')
    @classmethod
    def validate_scenario(cls, v):
        if not v or not v.strip():
            raise ValueError("scenario cannot be empty")
        return v.strip()

class DbImpactResponse(BaseModel):
    sla_violation: bool
    rto_violation: bool
    rpo_violation: bool
    expected_outage_time_minutes: int
    business_severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    why: list[str]
    recommendations: list[str]
    confidence: float
