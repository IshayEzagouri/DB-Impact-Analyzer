import json
import logging
import os
import time
from src.engine.models import DbScenarioRequest, BatchRequest, WhatIfRequest
from src.engine.reasoning import run_simulation
from src.engine.batch_analyzer import batch_analyze
from src.engine.what_if import what_if_analysis
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
        request_context = event.get("requestContext", {})
        # Use resourcePath from requestContext (API Gateway HTTP API v2 provides this)
        # Fallback to rawPath if resourcePath not available
        path = request_context.get("resourcePath", event.get("rawPath", "/"))
        route_key = request_context.get("routeKey", "UNKNOWN")
        http_method = request_context.get("http", {}).get("method", request_context.get("httpMethod", "UNKNOWN"))
        
        body_str = event.get("body", "{}")
        body = json.loads(body_str)
        
        # Log ALL path-related info for debugging
        logger.info(f"=== PATH DEBUG INFO ===")
        logger.info(f"resourcePath: {path}")
        logger.info(f"routeKey: {route_key}")
        logger.info(f"httpMethod: {http_method}")
        logger.info(f"requestContext: {json.dumps(request_context)}")
        logger.info(f"Body keys: {list(body.keys()) if isinstance(body, dict) else 'not a dict'}")
        logger.info(f"========================")
        
        # Normalize path - remove leading/trailing slashes for comparison
        normalized_path = path.rstrip("/") or "/"
        logger.info(f"Normalized path: {normalized_path}")
        
        # Detect batch request by body structure (most reliable)
        # Batch requests have 'db_identifiers' (plural), single have 'db_identifier' (singular)
        is_batch_by_body = "db_identifiers" in body and isinstance(body.get("db_identifiers"), list)
        is_single_by_body = "db_identifier" in body and not is_batch_by_body
        
        # Detect what-if request by body structure (has 'config_overrides')
        is_whatif_by_body = "config_overrides" in body and isinstance(body.get("config_overrides"), dict)
        
        # Check for batch-analyze route (path-based OR body-based detection)
        is_batch_path = normalized_path == "/batch-analyze" or normalized_path.endswith("/batch-analyze")
        
        # Check for what-if route (path-based OR body-based detection)
        is_whatif_path = normalized_path == "/what-if" or normalized_path.endswith("/what-if")
        
        if is_whatif_path or is_whatif_by_body:
            # What-if analysis route
            req = WhatIfRequest(**body)
            logger.info(f"What-if analysis for db={req.db_identifier}, scenario={req.scenario}, overrides={req.config_overrides}")
            what_if_response = what_if_analysis(req)
            return {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json"},
                "body": what_if_response.model_dump_json()
            }
        elif is_batch_path or is_batch_by_body:
            # Batch analysis route
            req = BatchRequest(**body)
            logger.info(f"Batch analysis for {len(req.db_identifiers)} databases, scenario={req.scenario}")
            response = batch_analyze(req)
            return {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json"},
                "body": response.model_dump_json()
            }
        elif normalized_path == "/" or is_single_by_body:
            # Single analysis route
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
            # Unknown route - include debug info in response
            debug_info = {
                "error": f"Unknown path: {path}",
                "debug": {
                    "resourcePath": path,
                    "normalizedPath": normalized_path,
                    "routeKey": route_key,
                    "httpMethod": http_method,
                    "bodyKeys": list(body.keys()) if isinstance(body, dict) else "not a dict"
                }
            }
            logger.error(f"Unknown route - {json.dumps(debug_info)}")
            return {
                "statusCode": 404,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps(debug_info)
            }
    except ValueError as e:
        # Include path debug info in validation errors to help diagnose routing issues
        request_context = event.get("requestContext", {})
        path = request_context.get("resourcePath", event.get("rawPath", "/"))
        route_key = request_context.get("routeKey", "UNKNOWN")
        error_response = {
            "error": str(e),
            "debug": {
                "resourcePath": path,
                "routeKey": route_key,
                "bodyKeys": list(json.loads(event.get("body", "{}")).keys()) if event.get("body") else "no body"
            }
        }
        logger.error(f"Validation error - {json.dumps(error_response)}")
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(error_response)
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
