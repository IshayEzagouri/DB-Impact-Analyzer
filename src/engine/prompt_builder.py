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
RDS FEATURE REFERENCE (use this when making recommendations):

Multi-AZ:
- If TRUE: Synchronous replication to standby instance in different availability zone
  * Automatic failover in 60-120 seconds if primary fails
  * Improves RTO (faster recovery) and RPO (near-zero data loss due to sync replication)
- If FALSE: Single instance - must restore from backup on failure
  * Recovery requires creating new instance and restoring from snapshot
  * Recommend enabling Multi-AZ to improve RTO and minimize data loss

PITR (Point-in-Time Recovery):
- If TRUE: Continuous transaction log backups stored automatically
  * Can restore to ANY second within retention period (not just daily snapshots)
  * Improves RPO from hours/days to seconds of data loss
- If FALSE: Only daily automated snapshots available
  * Can only restore to snapshot time (usually midnight)
  * Data loss = time since last snapshot (up to 24 hours)
  * Recommend enabling PITR to minimize data loss and improve RPO

Backup Retention:
- Number of DAYS of old backups kept (1-35 days)
- Does NOT affect data loss or RPO - only affects how far back you can restore
- Higher retention = can restore to older points in time (good for compliance/auditing)
- Lower retention = less storage cost, but can't restore to very old backups
- IMPORTANT: Increasing retention does NOT reduce data loss or improve RPO
  * Whether retention is 1 day or 7 days, data loss is the same if PITR is disabled
  * Only recommend increasing retention for compliance/audit needs, NOT for RPO

CRITICAL - When making recommendations:
- To improve RPO (reduce data loss): Recommend PITR, NOT higher backup retention
- To improve RTO (faster recovery): Recommend Multi-AZ, NOT higher backup retention
- Only recommend higher backup retention for compliance or audit requirements

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
- Compare predicted recovery time against RTO/RPO policies and QUANTIFY violations:
  * Example: "87 min recovery vs 30 min RTO = 57 min violation"
  * Example: "24 hours data loss vs 5 min RPO = policy exceeded by 288x"
- Explain data loss calculation based on configuration:
  * No Multi-AZ + No PITR: Data loss = time since last snapshot (up to 24 hours)
  * Multi-AZ + No PITR: Data loss = seconds (sync replication) but recovery still requires snapshot restore
  * Multi-AZ + PITR: Data loss = seconds, recovery = automatic failover in 60-120 seconds
- In recommendations, prioritize fixes by impact:
  * Multi-AZ improves BOTH RTO (failover) AND RPO (sync replication eliminates data loss)
  * PITR improves RPO (restore to any second) but doesn't help RTO (still need manual restore)
  * Enable both for maximum resilience
- If confidence < 0.7, you MUST return an uncertainty response instead
- Explain your reasoning clearly and quantitatively in the "why" array

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
