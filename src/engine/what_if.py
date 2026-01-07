from src.engine.models import DbScenarioRequest, WhatIfRequest, WhatIfResponse, DbImpactResponse, DbConfig
from src.engine.reasoning import run_simulation, call_bedrock
from src.engine.aws_state import get_real_db_state, get_fake_db_state, FAKE_DATABASES
from src.engine.business_context import load_business_context
from src.engine.prompt_builder import build_prompt
import logging
import os

logger = logging.getLogger(__name__)
IS_LAMBDA = os.getenv('AWS_EXECUTION_ENV') is not None


def what_if_analysis(request: WhatIfRequest) -> WhatIfResponse:
    if request.db_identifier in FAKE_DATABASES:
        baseline_db_state = get_fake_db_state(request.db_identifier)
    else:
        profile=None if IS_LAMBDA else 'develeap-ishay'
        baseline_db_state = get_real_db_state(request.db_identifier, profile_name=profile)
        
    baseline_request = DbScenarioRequest(db_identifier=request.db_identifier, scenario=request.scenario)
    # Pass baseline_db_state to avoid duplicate fetching
    baseline_analysis = run_simulation(baseline_request, db_state=baseline_db_state)
    
    what_if_db_state = baseline_db_state.model_copy(update=request.config_overrides)
    what_if_analysis = run_simulation(baseline_request, db_state=what_if_db_state, is_what_if=True, baseline_config=baseline_db_state)
    
    # Step 5: Calculate improvement_summary
    SEVERITY_ORDER = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
    
    baseline_severity_num = SEVERITY_ORDER[baseline_analysis.business_severity]
    what_if_severity_num = SEVERITY_ORDER[what_if_analysis.business_severity]
    
    severity_improved = what_if_severity_num < baseline_severity_num
    severity_change = f"{baseline_analysis.business_severity} -> {what_if_analysis.business_severity}"
    
    rto_reduction_minutes = baseline_analysis.expected_outage_time_minutes - what_if_analysis.expected_outage_time_minutes
    
    sla_violation_prevented = baseline_analysis.sla_violation and not what_if_analysis.sla_violation
    rto_violation_prevented = baseline_analysis.rto_violation and not what_if_analysis.rto_violation
    rpo_violation_prevented = baseline_analysis.rpo_violation and not what_if_analysis.rpo_violation
    
    improvement_summary = {
        "severity_improved": severity_improved,
        "severity_change": severity_change,
        "rto_reduction_minutes": rto_reduction_minutes,
        "sla_violation_prevented": sla_violation_prevented,
        "rto_violation_prevented": rto_violation_prevented,
        "rpo_violation_prevented": rpo_violation_prevented
    }
    
    # Step 6: Return WhatIfResponse
    return WhatIfResponse(
        baseline_analysis=baseline_analysis,
        what_if_analysis=what_if_analysis,
        improvement_summary=improvement_summary
    )
