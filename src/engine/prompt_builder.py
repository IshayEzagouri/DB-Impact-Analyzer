from src.engine.models import DbScenarioRequest
def build_prompt(
    request: DbScenarioRequest,
    db_state: dict,
    business_context: str
) -> str:
    """Build the assessment prompt for Bedrock."""

    prompt = f"""You are an expert Site Reliability Engineer analyzing database failure scenarios.

TASK:
Assess the impact if database "{request.db_identifier}" experiences a {request.scenario}.

You must answer these 5 critical questions:
1. sla_violation: Will this failure breach our SLA commitments? (true/false)
2. rto_violation: Will recovery time exceed our RTO policy? (true/false)
3. rpo_violation: Will data loss exceed our RPO policy? (true/false)
4. expected_outage_time_minutes: How long will we be down? (integer)
5. business_severity: How critical is this? (LOW/MEDIUM/HIGH/CRITICAL)

---
RDS CONFIGURATION:
{format_db_config(db_state)}

---
BUSINESS POLICIES & HISTORICAL DATA:
{business_context}

---
OUTPUT REQUIREMENTS:

Return ONLY valid JSON matching this exact schema:

{{
  "sla_violation": boolean,
  "rto_violation": boolean,
  "rpo_violation": boolean,
  "expected_outage_time_minutes": integer,
  "business_severity": "LOW" | "MEDIUM" | "HIGH" | "CRITICAL",
  "why": [array of strings explaining your reasoning],
  "recommendations": [array of strings with actionable fixes],
  "confidence": float between 0.0 and 1.0
}}

REASONING RULES:
- Base predictions on the ACTUAL configuration provided (not generic best practices)
- Use historical incident data to estimate recovery times:
  * PRIORITIZE specific incident times (e.g., "87 minutes on 2024-03-15") over general ranges
  * If only ranges are given (e.g., "60-90 minutes"), use the upper bound or average depending on confidence
  * Never estimate lower than observed historical times
- Compare predicted recovery time against RTO/RPO policies
- If confidence < 0.7, you MUST return an uncertainty response instead
- Explain your reasoning clearly in the "why" array

CONFIDENCE GUIDELINES:
- High (0.8-1.0): Direct historical data for this exact scenario
- Medium (0.6-0.79): Can extrapolate from similar scenarios
- Low (<0.6): Missing critical data, return uncertainty response

Return ONLY the JSON, no additional text.
"""

    return prompt


def format_db_config(db_state: dict) -> str:
    """Format DB config for the prompt."""
    return f"""
Database: {db_state['identifier']}
Engine: {db_state['engine']}
Instance Class: {db_state['instance_class']}
Multi-AZ: {db_state['multi_az']}
PITR Enabled: {db_state['pitr_enabled']}
Backup Retention: {db_state['backup_retention_days']} days
"""
