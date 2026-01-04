import json
import logging
import os
from src.engine.models import DbScenarioRequest
from src.engine.reasoning import run_simulation
logger = logging.getLogger()
logger.setLevel(logging.INFO)
def handler(event, context):
    logger.info(f"Received request for database simulation")
    expected_api_key = os.getenv("API_KEY")
    provided_api_key = event.get("headers", {}).get("x-api-key")
    if not expected_api_key:
        logger.error("API key not set")
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "API key not set"})
        }
    if provided_api_key != expected_api_key:
        logger.error(f"Unauthorized request with API key: {provided_api_key}")
        return {
            "statusCode": 401,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Unauthorized"})
        }
    try:
        body = json.loads(event["body"])
        req = DbScenarioRequest(**body)
        logger.info(f"Simulating failure for : {req.db_identifier}, scenario: {req.scenario}")
        response = run_simulation(req)
        logger.info(f"Simulation complete - Severity: {response.business_severity}, SLA violation: {response.sla_violation}")
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": response.model_dump_json()
        }
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}", exc_info=True)
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": str(e)})
        }