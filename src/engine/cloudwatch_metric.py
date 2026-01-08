import boto3
from botocore.config import Config
import logging
from src.engine.models import DbImpactResponse, BatchResponse, WhatIfResponse

logger = logging.getLogger(__name__)

# CloudWatch client with timeouts (shorter than Bedrock - metrics are fire-and-forget)
config = Config(connect_timeout=5, read_timeout=10)
cloudwatch = boto3.client('cloudwatch', region_name='us-east-1', config=config)
NAMESPACE = 'DBImpactAgent'  # Groups all metrics in CloudWatch console

def emit_analysis_metric(
    response: DbImpactResponse,
    duration_ms: float,
    scenario: str
):
    """Emit CloudWatch metrics for a single analysis operation."""
    try:
        # Send all metrics in one API call
        # Emit AnalysisCount 3 times with different dimension combinations
        # This allows dashboard to query by Severity only, Scenario only, or both
        cloudwatch.put_metric_data(
            Namespace=NAMESPACE,
            MetricData=[
                # AnalysisCount with both dimensions (for detailed analysis)
                {
                    'MetricName': 'AnalysisCount',
                    'Value': 1,
                    'Unit': 'Count',
                    'Dimensions': [
                        {'Name': 'Severity', 'Value': response.business_severity},
                        {'Name': 'Scenario', 'Value': scenario}
                    ]
                },
                # AnalysisCount with Severity only (for severity distribution widget)
                {
                    'MetricName': 'AnalysisCount',
                    'Value': 1,
                    'Unit': 'Count',
                    'Dimensions': [
                        {'Name': 'Severity', 'Value': response.business_severity}
                    ]
                },
                # AnalysisCount with Scenario only (for scenario usage widget)
                {
                    'MetricName': 'AnalysisCount',
                    'Value': 1,
                    'Unit': 'Count',
                    'Dimensions': [
                        {'Name': 'Scenario', 'Value': scenario}
                    ]
                },
                # AnalysisCount with NO dimensions (for total volume widget)
                {
                    'MetricName': 'AnalysisCount',
                    'Value': 1,
                    'Unit': 'Count'
                    # No Dimensions = rollup across all severities/scenarios
                },
                # Track analysis duration (global, not per scenario)
                {
                    'MetricName': 'AnalysisDuration',
                    'Value': duration_ms,
                    'Unit': 'Milliseconds'
                },
                # Track SLA violations (0/1, CloudWatch averages to get percentage)
                {
                    'MetricName': 'SLAViolationRate',
                    'Value': 1 if response.sla_violation else 0,
                    'Unit': 'None'
                },
                # Track RTO violations (global)
                {
                    'MetricName': 'RTOViolationRate',
                    'Value': 1 if response.rto_violation else 0,
                    'Unit': 'None'
                },
                # Track RPO violations (global)
                {
                    'MetricName': 'RPOViolationRate',
                    'Value': 1 if response.rpo_violation else 0,
                    'Unit': 'None'
                }
            ]
        )
        logger.info(f"CloudWatch metrics emitted: severity={response.business_severity}, scenario={scenario}, duration={duration_ms:.0f}ms")
    except Exception as e:
        # Fire-and-forget: metrics failure must not break analysis
        logger.error(f"Failed to emit CloudWatch metrics: {str(e)}")


def emit_batch_metric(
    batch_response: BatchResponse,
    duration_ms: float
):
    """Emit CloudWatch metrics for batch analysis operations."""
    try:
        # Calculate violation counts from batch results
        sla_violation_count = 0
        rto_violation_count = 0
        rpo_violation_count = 0
        
        for result in batch_response.results:
            if result.get("status") == "success" and "analysis" in result:
                analysis = result["analysis"]
                if analysis.get("sla_violation"):
                    sla_violation_count += 1
                if analysis.get("rto_violation"):
                    rto_violation_count += 1
                if analysis.get("rpo_violation"):
                    rpo_violation_count += 1
        
        # Send all 10 metrics in one API call
        cloudwatch.put_metric_data(
            Namespace=NAMESPACE,
            MetricData=[
                # Count batch operations
                {
                    'MetricName': 'BatchAnalysisCount',
                    'Value': 1,
                    'Unit': 'Count'
                },
                # Track batch size (number of databases analyzed)
                {
                    'MetricName': 'BatchSize',
                    'Value': batch_response.total_count,
                    'Unit': 'Count'
                },
                # Track severity distribution in batch
                {
                    'MetricName': 'BatchCriticalCount',
                    'Value': batch_response.critical_count,
                    'Unit': 'Count'
                },
                {
                    'MetricName': 'BatchHighCount',
                    'Value': batch_response.high_count,
                    'Unit': 'Count'
                },
                {
                    'MetricName': 'BatchMediumCount',
                    'Value': batch_response.medium_count,
                    'Unit': 'Count'
                },
                {
                    'MetricName': 'BatchLowCount',
                    'Value': batch_response.low_count,
                    'Unit': 'Count'
                },
                # Track violation counts in batch
                {
                    'MetricName': 'BatchSLAViolationCount',
                    'Value': sla_violation_count,
                    'Unit': 'Count'
                },
                {
                    'MetricName': 'BatchRTOViolationCount',
                    'Value': rto_violation_count,
                    'Unit': 'Count'
                },
                {
                    'MetricName': 'BatchRPOViolationCount',
                    'Value': rpo_violation_count,
                    'Unit': 'Count'
                },
                # Track batch duration
                {
                    'MetricName': 'BatchDuration',
                    'Value': duration_ms,
                    'Unit': 'Milliseconds'
                }
            ]
        )
        logger.info(f"CloudWatch batch metrics emitted: size={batch_response.total_count}, duration={duration_ms:.0f}ms")
    except Exception as e:
        # Fire-and-forget: metrics failure must not break analysis
        logger.error(f"Failed to emit CloudWatch batch metrics: {str(e)}")


def emit_what_if_metric(
    what_if_response: WhatIfResponse,
    duration_ms: float,
    scenario: str
):
    """Emit CloudWatch metrics for what-if analysis operations."""
    try:
        improvement = what_if_response.improvement_summary
        
        # Send all 7 metrics in one API call
        cloudwatch.put_metric_data(
            Namespace=NAMESPACE,
            MetricData=[
                # Count what-if operations (global, not per scenario)
                {
                    'MetricName': 'WhatIfAnalysisCount',
                    'Value': 1,
                    'Unit': 'Count'
                },
                # Track if severity improved (0 = no improvement, 1 = improved)
                {
                    'MetricName': 'WhatIfSeverityImproved',
                    'Value': 1 if improvement.get('severity_improved') else 0,
                    'Unit': 'None'
                },
                # Track RTO reduction (can be negative if what-if is worse)
                {
                    'MetricName': 'WhatIfRTOReduction',
                    'Value': improvement.get('rto_reduction_minutes', 0),
                    'Unit': 'None'
                },
                # Track if violations were prevented (0/1 for each type)
                {
                    'MetricName': 'WhatIfSLAViolationPrevented',
                    'Value': 1 if improvement.get('sla_violation_prevented') else 0,
                    'Unit': 'None'
                },
                {
                    'MetricName': 'WhatIfRTOViolationPrevented',
                    'Value': 1 if improvement.get('rto_violation_prevented') else 0,
                    'Unit': 'None'
                },
                {
                    'MetricName': 'WhatIfRPOViolationPrevented',
                    'Value': 1 if improvement.get('rpo_violation_prevented') else 0,
                    'Unit': 'None'
                },
                # Track what-if duration (includes both baseline + what-if analyses)
                {
                    'MetricName': 'WhatIfDuration',
                    'Value': duration_ms,
                    'Unit': 'Milliseconds'
                }
            ]
        )
        logger.info(f"CloudWatch what-if metrics emitted: scenario={scenario}, duration={duration_ms:.0f}ms")
    except Exception as e:
        # Fire-and-forget: metrics failure must not break analysis
        logger.error(f"Failed to emit CloudWatch what-if metrics: {str(e)}")