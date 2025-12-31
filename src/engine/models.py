from sre_parse import LITERAL
from pydantic import BaseModel
from typing import Literal
class DbScenarioRequest(BaseModel):
    db_identifier: str
    scenario: str = "primary_db_failure"

class DbImpactResponse(BaseModel):
    sla_violation: bool
    rto_violation: bool
    rpo_violation: bool
    expected_outage_time_minutes: int
    business_severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    why: list[str]
    recommendations: list[str]
    confidence: float
