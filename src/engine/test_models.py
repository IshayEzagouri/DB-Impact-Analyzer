from models import DbScenarioRequest, DbImpactResponse

# Test creating a request
request = DbScenarioRequest(db_identifier="prod-orders-db-01")
print ("Request:", request)

# Test creating a response
response = DbImpactResponse(
    sla_violation=True,
    rto_violation=True,
    rpo_violation=True,
    expected_outage_time_minutes=90,
    business_severity="CRITICAL",
    why=["No Multi-AZ", "Backups only once nightly"],
    recommendations=["Enable Multi-AZ", "Enable PITR"],
    confidence=0.86
)
print("Response:", response.model_dump_json(indent=2))