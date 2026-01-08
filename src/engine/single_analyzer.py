import logging
import time
from src.engine.models import DbScenarioRequest, DbImpactResponse
from src.engine.reasoning import run_simulation
from src.engine.cloudwatch_metric import emit_analysis_metric
logger = logging.getLogger(__name__)

def analyze(request: DbScenarioRequest) -> DbImpactResponse:
    start_time = time.time()
    logger.info(f"Starting single analysis for db={request.db_identifier}, scenario={request.scenario}")
    
    # Run the simulation (no caching - always get fresh results)
    response = run_simulation(request)
    total_time = (time.time() - start_time) * 1000
    logger.info(f"Single analysis complete in {total_time:.0f}ms - severity={response.business_severity}, sla_violation={response.sla_violation}")
    emit_analysis_metric(response, total_time, request.scenario)
    
    return response

