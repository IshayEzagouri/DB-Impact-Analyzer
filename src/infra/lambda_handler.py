import json
import logging
import os
import time
from src.engine.models import DbScenarioRequest, BatchRequest
from src.engine.reasoning import run_simulation
from src.engine.batch_analyzer import batch_analyze
logger = logging.getLogger()
logger.setLevel(logging.INFO)
CACHE={}


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
        return {
            "statusCode": 401,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Unauthorized"})
        }
    try:
        path = event.get("rawPath", "/")
        body_str = event.get("body", "{}")
        body = json.loads(body_str)
        
        # Log the path for debugging
        logger.info(f"Request path: {path}, body keys: {list(body.keys()) if isinstance(body, dict) else 'not a dict'}")
        
        # Check if this is a batch request by looking at the body (more reliable than path)
        # Batch requests have 'db_identifiers' (plural), single requests have 'db_identifier' (singular)
        is_batch_request = "db_identifiers" in body and isinstance(body.get("db_identifiers"), list)
        
        # Also check path as secondary indicator
        is_batch_path = "/batch-analyze" in path or path.endswith("batch-analyze")
        
        if is_batch_request or is_batch_path:
            req = BatchRequest(**body)
            logger.info(f"Batch analysis for {len(req.db_identifiers)} databases, scenario={req.scenario}")
            response = batch_analyze(req)
            return {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json"},
                "body": response.model_dump_json()
            }
        elif path == "/" or path == "/default" or "db_identifier" in body:
            # Single analysis request
            req = DbScenarioRequest(**body)
            logger.info(f"Simulating failure for : {req.db_identifier}, scenario: {req.scenario}")
            
            response = get_cached_or_run_simulation(req)
            
            logger.info(f"Simulation complete - Severity: {response.business_severity}, SLA violation: {response.sla_violation}")
            return {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json"},
                "body": response.model_dump_json()
            }
        else:
            return {
                "statusCode": 404,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": f"Unknown path: {path}"})
            }
    except ValueError as e:
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": str(e)})
        }
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}", exc_info=True)
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": str(e)})
        }
        
def get_cached_or_run_simulation(req: DbScenarioRequest):
    """
    Check cache for existing result, or run simulation and cache it.
    Returns DbImpactResponse.
    """
    # Create cache key from db_identifier and scenario
    cache_key = f"{req.db_identifier}#{req.scenario}"
    
    # Check if we have a cached result
    if cache_key in CACHE:
        cache_entry = CACHE[cache_key]
        # Check if cache is still valid (less than 600 seconds / 10 minutes old)
        if time.time() - cache_entry['ts'] < 600:
            logger.info(f"Cache HIT for {cache_key}")
            return cache_entry['response']
        else:
            # Cache expired, remove it
            logger.info(f"Cache EXPIRED for {cache_key}")
            del CACHE[cache_key]
    
    # No cache entry or expired, run simulation
    logger.info(f"Cache MISS for {cache_key}")
    response = run_simulation(req)
    # Store result in cache
    CACHE[cache_key] = {'response': response, 'ts': time.time()}
    return response
