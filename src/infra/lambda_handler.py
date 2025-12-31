import json
import logging
from src.engine.models import DbScenarioRequest
from src.engine.reasoning import run_simulation
logger = logging.getLogger()
logger.setLevel(logging.INFO)
def handler(event, context):
    logger.info(f"Recieved request for database simulation")
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