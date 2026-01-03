"""
Scenario Registry for DB Failure Impact Analysis

CRITICAL: All scenario prompts must follow constraints from architecture.md section 4.1.1:
- Only reference DB config fields and business docs (no app-specific logic)
- Use generic DB-level language (not application-specific)
- Leverage historical incident data from INCIDENT_HISTORY.md
- Assess DB-level severity, not business operations

Design Pattern:
- Each scenario is a dict with name, description, prompt_section, required_db_fields, tags
- prompt_section is injected into the main prompt by prompt_builder.py
- required_db_fields lists DB config fields needed for analysis
"""

# ==============================================================================
# SCENARIO DEFINITIONS
# ==============================================================================

SCENARIOS = {
    "primary_db_failure": {
        "name": "Primary Database Failure",
        "description": "Analyzes impact when primary DB instance fails completely (hardware failure, AZ outage, etc.)",
        "prompt_section": """
SCENARIO: Primary database instance has failed completely (hardware failure, AZ outage, or critical error).

ANALYSIS REQUIRED:
1. Check Multi-AZ configuration to determine failover capability:
   - Multi-AZ ENABLED → Automatic failover to standby in different AZ
     * Historical data shows Multi-AZ failovers complete in <5 minutes (see 2024-06-22 incident)
     * Estimate RTO: 3-5 minutes based on past incidents
     * Data loss: None (synchronous replication)

   - Multi-AZ DISABLED → Manual recovery required via snapshot restore
     * Historical data shows snapshot restores take 60-90 minutes for db.m5.large instances
     * Must create new instance and restore from most recent backup
     * Estimate RTO: 60-120 minutes based on instance class and past incidents (e.g., 2024-03-15: 87 min)
     * Data loss: Time since last backup (if PITR disabled)

2. Assess RPO (data loss) based on backup configuration:
   - PITR ENABLED → Can restore to any second within retention period
     * Data loss: Seconds to minutes (transaction logs captured continuously)

   - PITR DISABLED → Can only restore to snapshot time
     * Snapshots typically run once daily (usually overnight)
     * Data loss: Hours to 24 hours depending on when failure occurred
     * Example from 2024-03-15: ~18 hours data loss (backup from previous night)

3. Compare recovery time against RTO policy:
   - If Multi-AZ disabled AND RTO policy is <30 minutes → RTO violation
   - If Multi-AZ enabled AND RTO policy is <10 minutes → May still violate (failover takes 3-5 min)

4. Compare data loss against RPO policy:
   - If PITR disabled AND RPO policy is <1 hour → RPO violation likely
   - If PITR enabled → RPO typically met (seconds of data loss)

CRITICAL QUESTIONS TO ANSWER:
- Will this failure violate SLA thresholds based on expected downtime?
- Does estimated RTO exceed the acceptable recovery time from RTO policy?
- Does estimated RPO exceed the acceptable data loss from RPO policy?
- What is database-level severity (CRITICAL/HIGH/MEDIUM/LOW) based on:
  * Multi-AZ configuration (disabled = higher severity)
  * PITR configuration (disabled = higher data loss risk)
  * Business criticality from SLA policies
  * Historical incident patterns

RECOMMENDATIONS (prioritize by impact):
- If Multi-AZ disabled: Enable Multi-AZ to reduce RTO from 60-90 min to <5 min
- If PITR disabled: Enable PITR to reduce RPO from hours to seconds
- If backup retention < 7 days AND compliance requirements exist: Increase retention for audit purposes
- If instance class is small: Consider larger instance for faster backup/restore operations
""",
        "required_db_fields": ["multi_az", "pitr_enabled", "backup_retention_days", "instance_class"],
        "tags": ["availability", "disaster-recovery", "critical"]
    },

    "replica_lag": {
        "name": "Read Replica Lag",
        "description": "Analyzes impact when read replicas experience significant replication lag (>5 minutes behind primary)",
        "prompt_section": """
SCENARIO: Read replicas are experiencing significant replication lag (>5 minutes behind primary database).

ANALYSIS REQUIRED:
1. Check read replica configuration:
   - Number of read replicas available
   - Single replica = higher risk (if it lags, all read traffic affected)
   - Multiple replicas = can potentially route around lagging replica

2. Assess database-level impact of stale data:
   - Read-heavy workloads will receive stale data (>5 minutes old)
   - Write operations to primary are NOT affected (lag is one-way)
   - Applications reading from replicas may show inconsistent data
   - User-facing reads may display outdated information

3. Review historical patterns from INCIDENT_HISTORY.md:
   - Check if past replica lag incidents are documented
   - Estimate resolution time based on historical data
   - If no historical data: Replica lag typically resolves in 10-30 minutes depending on cause

4. Evaluate severity based on business policies:
   - Check SLA policies for data consistency requirements
   - If SLA requires "real-time data" or "eventual consistency <1 min" → SLA violation
   - If business operations depend on accurate reads → Higher severity
   - Development/analytics workloads → Lower severity (stale data acceptable)

5. Assess if lag affects availability:
   - Primary database still operational (writes continue)
   - Only read operations affected
   - Typically MEDIUM severity unless business requires real-time reads

CRITICAL QUESTIONS TO ANSWER:
- Does replication lag duration violate data consistency SLAs from business policies?
- What is database-level severity (CRITICAL/HIGH/MEDIUM/LOW) based on:
  * Number of replicas (fewer = higher risk)
  * Business data freshness requirements from SLA policies
  * Historical lag incident resolution times
- Will applications fail or show incorrect data due to staleness?
- Is this a temporary spike or sustained lag (affects urgency)?

RECOMMENDATIONS:
- If single replica: Add additional read replicas for redundancy
- If sustained lag: Investigate primary database load and optimize queries
- If lag is recurring: Consider vertical scaling of replica instance class
- If business requires real-time reads: Implement read-through cache or route critical reads to primary
- Monitor replication lag metrics and set up alerts at 2-minute threshold
""",
        "required_db_fields": ["read_replicas", "instance_class", "engine"],
        "tags": ["performance", "read-scaling", "data-consistency"]
    },

    "backup_failure": {
        "name": "Backup Failure",
        "description": "Analyzes impact when automated backups fail or latest backup is corrupted/unusable",
        "prompt_section": """
SCENARIO: Automated database backups have failed, or the latest backup is corrupted and unusable.

ANALYSIS REQUIRED:
1. Assess current exposure if primary database fails NOW:
   - With no recent backup: Must rely on older backup (data loss = time since last good backup)
   - If PITR enabled: Transaction logs may still allow point-in-time recovery (partial mitigation)
   - If PITR disabled: Complete data loss back to last successful backup

2. Calculate maximum data loss exposure (RPO):
   - Check backup_retention_days to find age of last known-good backup
   - If last good backup is 2+ days old → Potential data loss of 48+ hours
   - Compare against RPO policy threshold (typically 1-4 hours for production DBs)
   - If exposure exceeds RPO policy → RPO violation risk

3. Evaluate recovery capability:
   - Multi-AZ: Still provides failover but doesn't protect against data corruption
   - If primary fails AND backup is unusable → Catastrophic data loss scenario
   - If PITR is enabled: Can recover to any point using transaction logs (good safety net)

4. Check compliance and regulatory requirements:
   - Backup failures may violate compliance policies (SOC2, HIPAA, GDPR, etc.)
   - Review business policies for backup SLA requirements
   - Some industries require daily successful backups by regulation

5. Assess urgency and severity:

   If PITR enabled: Transaction logs still provide point-in-time recovery
     - Backup failure is less critical (still has recent recovery points)
     - Severity: HIGH (not CRITICAL) - has safety net

   If PITR disabled: Backup failure is catastrophic
     - Data loss = time since last successful backup
     - Severity: CRITICAL - no safety net

   - CRITICAL if: Production database + No PITR + RPO policy strict (<1 hour)
   - HIGH if: Production database + PITR enabled (some protection remains)
   - MEDIUM if: Development/staging database + Recent backups exist
   - Calculate business_severity based on exposure window and business criticality

CRITICAL QUESTIONS TO ANSWER:
- What is maximum potential data loss (RPO) if primary database fails right now?
- Does this backup failure violate backup/recovery SLAs from business policies?
- What is business_severity (CRITICAL/HIGH/MEDIUM/LOW) based on:
  * Age of last known-good backup
  * PITR status (enabled = partial mitigation)
  * Business criticality tier from SLA policies
  * Compliance requirements
- Are there alternative recovery mechanisms available (PITR, read replicas)?
- How quickly must this be resolved to avoid SLA/compliance violations?

RECOMMENDATIONS (prioritize by urgency):
- URGENT: Investigate and fix backup failure immediately (check disk space, permissions, backup window)
- If PITR disabled: Enable PITR immediately as safety net while fixing backups
- If compliance-critical: Notify compliance team and document incident
- If backup retention is low (<7 days): Increase retention to provide wider recovery window
- Implement backup monitoring and alerting (alert on first failure, not just repeated failures)
- Test backup restoration regularly (quarterly) to catch corruption early
""",
        "required_db_fields": ["backup_retention_days", "pitr_enabled", "multi_az"],
        "tags": ["disaster-recovery", "compliance", "data-protection", "critical"]
    },

    "storage_pressure": {
        "name": "Storage Pressure",
        "description": "Analyzes impact when database storage utilization reaches 85%+ of allocated capacity",
        "prompt_section": """
SCENARIO: Database storage utilization has reached 85%+ of allocated capacity.

ANALYSIS REQUIRED:
1. Calculate remaining capacity and urgency:
   - Check allocated_storage and current utilization (assume 85%+)
   - Remaining capacity = allocated_storage * 0.15 (15% headroom left)
   - If max_allocated_storage is set AND less than 100% full → Autoscaling will trigger
   - If max_allocated_storage is NOT set OR already at max → Manual intervention required

2. Estimate time until storage exhaustion:
   - Cannot calculate exact time (requires growth rate metrics - not available per 4.1.1)
   - Use generic severity assessment: 85% = WARNING, 90%+ = CRITICAL
   - Historical patterns: Storage typically grows 5-10% per month for active DBs
   - At 85% utilization, estimate DAYS to weeks until full (not hours)

3. Assess impact when storage reaches 100%:
   - Database-level impact: Write operations FAIL (database cannot accept new data)
   - Read operations continue to work
   - Database may crash or become unresponsive
   - Transaction logs may fill up, causing replication lag or failure
   - Backups may fail (need space for snapshots)
   - CRITICAL severity if this occurs

4. Check autoscaling configuration:
   - If max_allocated_storage > allocated_storage → RDS will auto-scale before 100%
     * Auto-scaling triggers at ~90% utilization or 10GB free (whichever is less)
     * Reduces urgency to MEDIUM (system will self-heal)

   - If max_allocated_storage NOT set OR already at maximum → HIGH/CRITICAL urgency
     * Manual intervention required immediately
     * Risk of database outage if storage fills completely

5. Evaluate business impact severity:
   - Check SLA policies for availability requirements
   - Storage exhaustion = database outage = SLA violation
   - Compare against RTO policy: Manual storage expansion takes 15-30 minutes
   - If autoscaling enabled: No expected outage (seamless expansion)

CRITICAL QUESTIONS TO ANSWER:
- How soon until storage is exhausted (hours/days/weeks based on 85% utilization)?
- Will storage exhaustion cause database outage and write failures?
- Does this violate availability SLAs from business policies?
- What is business_severity (CRITICAL/HIGH/MEDIUM/LOW) based on:
  * Current utilization percentage (85% vs 95% vs 99%)
  * Autoscaling configuration (enabled = lower severity)
  * Business criticality tier from SLA policies
  * Time sensitivity (production vs dev environment)
- Is autoscaling configured, or is manual intervention required?

RECOMMENDATIONS (prioritize by urgency):
- If max_allocated_storage NOT set: Enable storage autoscaling immediately
  * Set max_allocated_storage to 2-3x current allocated_storage
  * Prevents outages from unexpected growth

- If already at max_allocated_storage: Increase max limit or upgrade to larger storage type

- If 90%+ utilized: URGENT manual expansion required (don't wait for autoscaling)
  * Add 50-100% more capacity to provide headroom

- Long-term: Implement storage monitoring and alerting at 70% threshold (not 85%)

- Long-term: Investigate storage growth patterns and archive/purge old data

- If frequent storage pressure: Consider data lifecycle policies or table partitioning
""",
        "required_db_fields": ["allocated_storage", "max_allocated_storage", "engine", "instance_class"],
        "tags": ["capacity", "availability", "operational"]
    }
}


# UTILITY FUNCTIONS
# ==============================================================================

#For UI
def list_scenarios():
    results = []
    for scenario_id, scenario in SCENARIOS.items():
        results.append({
            'id': scenario_id,
            'name': scenario['name'],
            'description': scenario['description'],
            'tags': scenario['tags']
        })
    return results


#For prompt builder
def get_scenario(scenario_id: str):
    if scenario_id not in SCENARIOS:
        raise ValueError(f"Scenario {scenario_id} not found")
    return SCENARIOS[scenario_id]
    

#For prompt builder
def validate_scenario(scenario_id: str) -> bool:
    return scenario_id in SCENARIOS

