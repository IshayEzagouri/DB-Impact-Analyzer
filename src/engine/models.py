from pydantic import BaseModel, field_validator
from typing import Literal
from src.engine.scenarios import validate_scenario
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
    def validate_scenario_exists(cls, v):
        if not validate_scenario(v):
            raise ValueError(f"Invalid scenario: {v}")
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

class BatchRequest(BaseModel):
    db_identifiers: list[str]
    scenario: str = "primary_db_failure"

    @field_validator('db_identifiers')
    @classmethod
    def validate_batch_size(cls, v):
        if len(v) > 50:
            raise ValueError(f"Batch size {len(v)} exceeds maximum of 50 databases. Split into multiple batches.")
        if len(v) == 0:
            raise ValueError("At least one database identifier required")
        return v

    @field_validator('scenario')
    @classmethod
    def validate_scenario(cls, v):
        from src.engine.scenarios import SCENARIOS
        if v not in SCENARIOS:
            raise ValueError(f"Invalid scenario '{v}'")
        return v

class BatchResponse(BaseModel):
    total_count: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    results: list[dict]  # [{db_identifier, status, analysis/error}]
    
    
class WhatIfRequest(BaseModel):
    db_identifier: str
    scenario: str="primary_db_failure"
    config_overrides: dict
    
    @field_validator('config_overrides')
    @classmethod
    def validate_config_overrides(cls, v):
        if not v:
            raise ValueError("config_overrides cannot be empty. Provide at least one configuration change.")
        
        valid_fields = [
            "multi_az",
            "backup_retention_days",
            "storage_encrypted",
            "instance_class",
            "allocated_storage",
            "max_allocated_storage",
            "read_replicas",
            "auto_minor_version_upgrade"
        ]
        
        # Check each key in config_overrides is valid
        for key in v.keys():  # Iterate over keys in the dict, not valid_fields
            if key not in valid_fields:
                raise ValueError(f"Invalid config field '{key}'. Valid fields: {', '.join(valid_fields)}")
        return v  # Return outside the loop
        
    @field_validator('scenario')
    @classmethod
    def validate_scenario(cls, v):
        if not validate_scenario(v):
            raise ValueError(f"Invalid scenario: {v}")
        return v
    @field_validator('db_identifier')
    @classmethod
    def validate_db_identifier(cls, v):
        if not v or not v.strip():
            raise ValueError("db_identifier cannot be empty")
        return v.strip()
    
class WhatIfResponse(BaseModel):
    baseline_analysis: DbImpactResponse
    what_if_analysis: DbImpactResponse
    improvement_summary: dict