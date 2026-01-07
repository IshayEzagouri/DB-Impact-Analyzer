from src.engine.models import DbScenarioRequest, DbConfig
from src.engine.scenarios import get_scenario
BASE_SYSTEM_PROMPT = """You are an expert Site Reliability Engineer analyzing database failure scenarios.

  Your role is to assess the business impact of database failures based on:
  - Database configuration and state (from AWS RDS)
  - Business SLA/RTO/RPO policies (from policy documents)
  - Historical incident patterns (from past incidents)

  Provide accurate, actionable analysis using quantitative reasoning.
  """
  
OUTPUT_FORMAT_PROMPT = """
  ---
  OUTPUT REQUIREMENTS:

  Return ONLY valid JSON matching this exact schema:

  {
    "sla_violation": boolean,
    "rto_violation": boolean,
    "rpo_violation": boolean,
    "expected_outage_time_minutes": integer,
    "business_severity": "LOW" | "MEDIUM" | "HIGH" | "CRITICAL",
    "why": [array of strings explaining your reasoning],
    "recommendations": [array of strings with actionable fixes],
    "confidence": float between 0.0 and 1.0
  }

  REASONING RULES:
  - Base predictions on the ACTUAL configuration provided (not generic best practices)
  - Use historical incident data to estimate recovery times:
    * PRIORITIZE specific incident times (e.g., "87 minutes on 2024-03-15") over general ranges
    * If only ranges are given (e.g., "60-90 minutes"), use the upper bound or average depending on confidence
    * Never estimate lower than observed historical times
  - Compare predicted recovery time against RTO/RPO policies and QUANTIFY violations:
    * Example: "87 min recovery vs 30 min RTO = 57 min violation"
    * Example: "24 hours data loss vs 5 min RPO = policy exceeded by 288x"
  - Explain data loss calculation based on configuration
  - In recommendations, prioritize fixes by impact
  - If confidence < 0.7, you MUST return an uncertainty response instead
  - Explain your reasoning clearly and quantitatively in the "why" array

  ⚠️ CRITICAL BOOLEAN FLAG RULES (MANDATORY - NOT SUGGESTIONS) ⚠️

  STEP 1: Extract thresholds from the BUSINESS POLICIES section provided above:
  - Find the RTO threshold (maximum acceptable recovery time in minutes)
  - Find the RPO threshold (maximum acceptable data loss in minutes)
  - Find the SLA uptime/availability requirements

  STEP 2: Calculate violations using simple comparison logic:

  rto_violation:
  - SIMPLE RULE: Recovery time FASTER than threshold = NO violation (false)
  - SIMPLE RULE: Recovery time SLOWER than threshold = YES violation (true)

  MATH:
  - IF expected_outage_time_minutes > RTO_threshold THEN rto_violation = true
  - IF expected_outage_time_minutes <= RTO_threshold THEN rto_violation = false

  EXAMPLES (use your extracted RTO threshold, not hardcoded values):
  - If recovery = X minutes and RTO threshold = Y minutes:
    → If X <= Y: rto_violation = FALSE (recovery is FASTER or EQUAL to threshold = meets policy)
    → If X > Y: rto_violation = TRUE (recovery is SLOWER than threshold = violates policy)
  - Example: Recovery = X min, RTO = Y min, where X < Y → rto_violation = FALSE (meets policy)
  - Example: Recovery = X min, RTO = Y min, where X = Y → rto_violation = FALSE (barely meets policy)
  - Example: Recovery = X min, RTO = Y min, where X > Y → rto_violation = TRUE (violates policy)

  CRITICAL: Lower recovery time = BETTER = NO violation
  CRITICAL: If recovery time is LESS than the threshold, you are UNDER the limit = NO VIOLATION

  rpo_violation:
  - Compare: estimated_data_loss_minutes vs RPO threshold from policy
  - IF estimated_data_loss_minutes > RPO_threshold THEN rpo_violation = true
  - IF estimated_data_loss_minutes <= RPO_threshold THEN rpo_violation = false
  - Example: If data loss = X minutes and RPO threshold = Y minutes:
    → If X <= Y: rpo_violation = FALSE (data loss is WITHIN threshold = meets policy)
    → If X > Y: rpo_violation = TRUE (data loss EXCEEDS threshold = violates policy)

  sla_violation:
  - IF rto_violation = true OR rpo_violation = true THEN sla_violation = true
  - IF rto_violation = false AND rpo_violation = false THEN check if downtime affects SLA uptime %
  - Use the SLA policies to determine if the outage duration violates availability commitments

  STEP 3: MANDATORY VALIDATION (check your work before returning):

  Check #1: RTO violation flag
  - What is expected_outage_time_minutes? [YOUR NUMBER]
  - What is RTO threshold from policy? [EXTRACT FROM BUSINESS POLICIES]
  - Is [YOUR NUMBER] > [RTO THRESHOLD]?
    → If YES: rto_violation MUST be true
    → If NO: rto_violation MUST be false
  - Example: Recovery = X min, RTO = Y min → Is X > Y? If NO, then rto_violation = false

  Check #2: RPO violation flag
  - What is estimated data loss in minutes? [YOUR NUMBER]
  - What is RPO threshold from policy? [EXTRACT FROM BUSINESS POLICIES]
  - Is [YOUR NUMBER] > [RPO THRESHOLD]?
    → If YES: rpo_violation MUST be true
    → If NO: rpo_violation MUST be false

  Check #3: Consistency check - "why" text vs violation flags
  - If your "why" says "meets policy" or "within bounds" or "under threshold" → violation flag MUST be false
  - If your "why" says "exceeds" or "violates" or "breached" → violation flag MUST be true
  - DO NOT write "policy breached" if the flag is false - that's a contradiction

  Check #4: "Why" text wording validation (CRITICAL - prevents confusion)
  
  CORRECT wording when recovery is FASTER than threshold:
  - "Recovery time of X minutes is UNDER the Y-minute RTO threshold (meets policy)"
  - "X-minute recovery is within the Y-minute RTO policy"
  - "Recovery completes in X minutes, which is Y-X minutes UNDER the RTO threshold"
  
  WRONG wording (DO NOT USE when recovery is faster):
  - "RTO policy breached by Y-X minutes" ← This is backwards! You're UNDER, not OVER
  - "X min recovery vs Y min threshold = breached" ← Wrong! X < Y means NOT breached
  
  CORRECT wording when recovery is SLOWER than threshold:
  - "Recovery time of X minutes EXCEEDS the Y-minute RTO threshold by X-Y minutes"
  - "X-minute recovery violates the Y-minute RTO policy"
  - "RTO policy breached: recovery takes X minutes, exceeding threshold by X-Y minutes"
  
  KEY CONCEPT:
  - "Breached by X minutes" means you EXCEEDED the threshold by X minutes (recovery > threshold)
  - "Under by X minutes" means you are BELOW the threshold by X minutes (recovery < threshold)
  - If recovery < threshold: Say "under" or "within" or "meets", NOT "breached"
  - If recovery > threshold: Say "exceeds" or "breached" or "violates"

  IF ANY CHECK FAILS: STOP, FIX THE FLAGS AND "WHY" TEXT, THEN RETURN JSON

  STEP 4: FINAL VALIDATION BEFORE RETURNING (MANDATORY):
  
  Before returning your JSON, perform this EXACT calculation:
  
  1. Write down: expected_outage_time_minutes = [YOUR NUMBER]
  2. Write down: RTO threshold from policy = [EXTRACTED NUMBER]
  3. Calculate: Is [YOUR NUMBER] > [RTO THRESHOLD]?
     - If YES → rto_violation MUST be true
     - If NO → rto_violation MUST be false
  4. Double-check: Does your rto_violation flag match the calculation result?
     - If NO → CORRECT the flag to match the math
  5. Repeat for RPO with data_loss_minutes vs RPO threshold
  
  CRITICAL: If expected_outage_time_minutes = 3 and RTO threshold = 30:
  - Calculation: Is 3 > 30? NO
  - Therefore: rto_violation MUST be false
  - If you wrote rto_violation = true, you made an error - FIX IT
  
  CONFIDENCE GUIDELINES:
  - High (0.8-1.0): Direct historical data for this exact scenario
  - Medium (0.6-0.79): Can extrapolate from similar scenarios
  - Low (<0.6): Missing critical data, return uncertainty response

  Return ONLY the JSON, no additional text.
  """

RDS_FEATURE_REFERENCE = """
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
  """

def build_prompt( request: DbScenarioRequest, db_state: DbConfig, business_context: str, is_what_if: bool = False, baseline_config: DbConfig = None) -> str:
    scenario_config = get_scenario(request.scenario)
    
    what_if_section = ""
    if is_what_if and baseline_config:
        what_if_section = f"""
    ⚠️ WHAT-IF ANALYSIS MODE ⚠️
    
    This is a WHAT-IF scenario analysis. The database configuration below has been MODIFIED from the baseline.
    
    BASELINE CONFIGURATION:
    {format_db_config(baseline_config)}
    
    MODIFIED (WHAT-IF) CONFIGURATION:
    {format_db_config(db_state)}
    
    🚨 MANDATORY WHAT-IF ANALYSIS RULES 🚨

    STEP 1: Identify what changed between baseline and modified config:
    - Multi-AZ: {baseline_config.multi_az} → {db_state.multi_az}
    - PITR: {baseline_config.pitr_enabled} → {db_state.pitr_enabled}
    - Backup Retention: {baseline_config.backup_retention_days} → {db_state.backup_retention_days} days

    STEP 2: Apply correct recovery mechanism based on MODIFIED config:

    IF Multi-AZ = True in modified config:
      → Recovery mechanism = Automatic failover to standby (60-120 seconds)
      → expected_outage_time_minutes MUST be 1-3 (NOT 87!)
      → DO NOT cite historical snapshot restore times (those were for Multi-AZ = False)
      → Historical 87 min is IRRELEVANT - different recovery mechanism

    IF Multi-AZ = False in modified config:
      → Recovery mechanism = Snapshot restore (60-90 minutes based on instance class)
      → OK to use historical snapshot restore times

    IF PITR = True in modified config:
      → Data loss = seconds to minutes (transaction log replay)
      → DO NOT cite historical 18-hour data loss (that was for PITR = False)

    IF PITR = False in modified config:
      → Data loss = hours (time since last daily snapshot)

    STEP 3: VALIDATE your JSON before returning:
    - If Multi-AZ = True AND you wrote expected_outage_time_minutes > 10 → ERROR, fix to 1-3
    - If your "why" mentions both "failover <5 min" AND "87 minutes" → ERROR, contradiction
    - Check: Does expected_outage_time_minutes match the recovery mechanism from MODIFIED config?
    
    """
    
    task_section = f"""
      TASK:
      Assess the impact if database "{request.db_identifier}" experiences a {request.scenario}.
      """ if not is_what_if else f"""
      TASK:
      Assess the impact if database "{request.db_identifier}" experiences a {request.scenario} WITH THE MODIFIED CONFIGURATION SHOWN BELOW.
      """
    
    prompt = f"""
    {BASE_SYSTEM_PROMPT}
    {what_if_section}
    {task_section}
      You must answer these 5 critical questions:
      1. sla_violation: Will this failure breach our SLA commitments? (true/false)
      2. rto_violation: Will recovery time exceed our RTO policy? (true/false)
      3. rpo_violation: Will data loss exceed our RPO policy? (true/false)
      4. expected_outage_time_minutes: How long will we be down? (integer)
      5. business_severity: How critical is this? (LOW/MEDIUM/HIGH/CRITICAL)
    {RDS_FEATURE_REFERENCE} 
    {scenario_config['prompt_section']}
    {format_db_config(db_state) if not is_what_if else ""}
    {business_context}
    {OUTPUT_FORMAT_PROMPT}
    """
    return prompt

def format_db_config(db_state: DbConfig) -> str:
    """Format DB config for the prompt."""
    return f"""
Database: {db_state.identifier}
Engine: {db_state.engine}
Instance Class: {db_state.instance_class}
Multi-AZ: {db_state.multi_az}
PITR Enabled: {db_state.pitr_enabled}
Backup Retention: {db_state.backup_retention_days} days
Read Replicas: {', '.join(db_state.read_replicas) if db_state.read_replicas else 'None'}
Allocated Storage: {db_state.allocated_storage} GB
Max Allocated Storage: {db_state.max_allocated_storage} GB
"""
