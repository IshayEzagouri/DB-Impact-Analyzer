from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict
import logging
import time
from src.engine.models import DbScenarioRequest, BatchRequest, BatchResponse
from src.engine.reasoning import run_simulation
from src.engine.cloudwatch_metric import emit_batch_metric

logger = logging.getLogger(__name__)

def batch_analyze(request: BatchRequest) -> BatchResponse:
    start_time = time.time()
    logger.info(f"Starting batch analysis for {len(request.db_identifiers)} databases, scenario={request.scenario}")
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_db={}
        for db_identifier in request.db_identifiers:
            db_request = DbScenarioRequest(db_identifier=db_identifier, scenario=request.scenario)
            future=executor.submit(run_simulation, db_request)
            future_to_db[future]=db_identifier
        severity_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
        results=[]
        for future in as_completed(future_to_db.keys()):
            db_identifier=future_to_db[future]
            try:
                result=future.result()
                severity_counts[result.business_severity] += 1
                results.append({
                    "db_identifier": db_identifier,
                    "status": "success",
                    "analysis": result.model_dump()
                })
            except Exception as e:
                results.append({
                "db_identifier": db_identifier,
                "status": "error",
                "error": str(e)
})
        severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "ERROR": 4}

        results.sort(
            key=lambda r: severity_order.get(
                r.get("analysis", {}).get("business_severity", "ERROR")
                if r.get("status") == "success" else "ERROR",
                4
            )
        )
        total_time=(time.time() - start_time) * 1000
        logger.info(f"Batch analysis complete: {len(results)} databases in {total_time:.0f}ms")
        
    batch_response = BatchResponse(
        total_count=len(results),
        critical_count=severity_counts["CRITICAL"],
        high_count=severity_counts["HIGH"],
        medium_count=severity_counts["MEDIUM"],
        low_count=severity_counts["LOW"],
        results=results
    )
    emit_batch_metric(batch_response, total_time)
    return batch_response