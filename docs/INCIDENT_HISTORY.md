# Database Incident History

## Primary Database Failures

### 2024-03-15: prod-orders-db-01 Primary Failure
- **Cause:** Hardware failure (AWS-side)
- **Configuration:** Single-AZ, daily snapshots only (no PITR)
- **Recovery time:** 87 minutes (manual snapshot restore to new instance)
- **Data loss:** ~18 hours (last backup was from previous night at 2am)
- **Business impact:** SLA violated (99.9% uptime breached), order processing stopped
- **Severity:** CRITICAL
- **Lessons learned:** Single-AZ + no PITR = unacceptable RTO/RPO for production

### 2024-06-22: prod-users-db Multi-AZ Failover
- **Cause:** AZ outage (us-east-1a complete failure)
- **Configuration:** Multi-AZ enabled, PITR enabled
- **Recovery time:** 3 minutes (automatic failover to standby in us-east-1b)
- **Data loss:** None (synchronous replication)
- **Business impact:** Brief service degradation, no SLA violation
- **Severity:** MEDIUM
- **Lessons learned:** Multi-AZ works as designed, <5 min failover is reliable

### 2024-08-10: dev-analytics-db Instance Crash
- **Cause:** Out-of-memory error (runaway query)
- **Configuration:** Single-AZ, PITR enabled, 7-day retention
- **Recovery time:** 12 minutes (automatic instance restart)
- **Data loss:** ~30 seconds (PITR transaction logs protected data)
- **Business impact:** Development environment only, no production impact
- **Severity:** LOW
- **Lessons learned:** PITR is critical even for dev DBs to minimize data loss

---

## Read Replica Lag Incidents

### 2024-05-18: prod-orders-db-01 Replica Lag Spike (HISTORICAL - Replicas Decommissioned)
- **Cause:** Large batch insert on primary (50GB data load)
- **Configuration at time of incident:** 2 read replicas (db.m5.large), asynchronous replication
- **Current configuration:** NO read replicas (decommissioned in Q4 2024 due to cost optimization)
- **Peak lag:** 12 minutes behind primary
- **Resolution time:** 23 minutes (lag cleared after batch job completed)
- **Business impact:** Analytics dashboard showed stale order counts, customer complaints
- **Severity:** MEDIUM
- **Mitigation:** Routed read traffic to primary temporarily
- **Lessons learned:** Large writes cause predictable lag, need read replica monitoring
- **Post-incident change:** Replicas removed; all reads now hit primary database directly

### 2024-07-09: prod-users-db Replication Stall (HISTORICAL - Replica Decommissioned)
- **Cause:** Network congestion between AZs
- **Configuration at time of incident:** Single read replica (db.t3.medium)
- **Current configuration:** NO read replicas (decommissioned in Q4 2024, Multi-AZ handles availability)
- **Peak lag:** 8 minutes behind primary
- **Resolution time:** 15 minutes (AWS resolved network issue)
- **Business impact:** User profile reads showed outdated data, minimal customer impact
- **Severity:** LOW
- **Lessons learned:** Multiple replicas provide redundancy during single replica issues
- **Post-incident change:** Replica removed; Multi-AZ configuration provides sufficient availability

### 2024-09-30: prod-inventory-db Sustained Lag
- **Cause:** Undersized replica instance (db.t3.small handling production read load)
- **Configuration:** Single read replica, severely undersized
- **Peak lag:** 45 minutes behind primary (sustained)
- **Resolution time:** 3 hours (required replica instance class upgrade to db.m5.large)
- **Business impact:** Inventory counts severely stale, order fulfillment errors
- **Severity:** HIGH
- **Lessons learned:** Replicas must be sized appropriately for read workload

---

## Backup and Recovery Incidents

### 2024-04-12: prod-payments-db Backup Failure
- **Cause:** S3 backup bucket reached quota limit
- **Configuration:** 30-day backup retention, automated snapshots
- **Duration:** 3 consecutive backup failures (3 days unnoticed)
- **Recovery impact:** If primary had failed, max data loss = 72 hours
- **Resolution:** Increased S3 quota, enabled backup failure alerts
- **Severity:** HIGH (exposure risk, not actual outage)
- **Lessons learned:** Backup monitoring is critical, failures must alert immediately

### 2024-10-05: dev-testing-db Corrupted Snapshot
- **Cause:** Snapshot taken during schema migration, inconsistent state
- **Configuration:** Daily snapshots, 7-day retention, no PITR
- **Impact:** Latest 2 snapshots were corrupted/unusable
- **Fallback:** Restored from 3-day-old snapshot (72 hours data loss)
- **Business impact:** Development environment only, lost 3 days of test data
- **Severity:** LOW
- **Lessons learned:** Enable PITR as safety net, test snapshot restores regularly

---

## Storage Capacity Incidents

### 2024-02-28: prod-logs-db Storage Exhaustion
- **Cause:** Application logging explosion (debug mode left on), no autoscaling configured
- **Configuration:** 500GB allocated, max_allocated_storage NOT set
- **Timeline:**
  - 85% utilization reached at 9am
  - 95% utilization at 11am
  - 100% (full) at 2pm
- **Outage duration:** 45 minutes (manual storage expansion from 500GB to 1TB)
- **Business impact:** Log ingestion stopped, write operations failed, monitoring blind
- **Severity:** HIGH
- **Lessons learned:** ALWAYS configure max_allocated_storage for autoscaling

### 2024-11-12: prod-orders-db Storage Autoscaling Event
- **Cause:** Black Friday traffic surge, normal growth
- **Configuration:** 1TB allocated, max_allocated_storage = 5TB (autoscaling enabled)
- **Timeline:**
  - 85% utilization reached at 6am
  - 90% utilization at 10am
  - RDS auto-scaled from 1TB to 1.5TB at 10:15am (seamless)
- **Downtime:** None (online storage expansion)
- **Business impact:** No impact, system self-healed
- **Severity:** LOW (informational, not an incident)
- **Lessons learned:** Storage autoscaling works as designed, prevents outages

---

## Key Learnings and Patterns

### Recovery Time Objectives (RTO)
- **Multi-AZ failover:** 2-5 minutes (median: 3 minutes, P95: 5 minutes)
- **Single-AZ snapshot restore:**
  - db.t3.medium: 45-60 minutes
  - db.m5.large: 60-90 minutes
  - db.m5.xlarge: 75-120 minutes
- **Instance restart (crash recovery):** 5-15 minutes
- **Manual storage expansion:** 30-60 minutes downtime

### Recovery Point Objectives (RPO)
- **Multi-AZ with PITR:** 0-30 seconds data loss
- **Single-AZ with PITR:** 30 seconds to 5 minutes (transaction log replay)
- **Daily snapshots only (no PITR):** Up to 24 hours data loss
- **Backup failure scenario:** Data loss = time since last successful backup

### Replica Lag Patterns
- **Normal replication lag:** <5 seconds (asynchronous replication)
- **During large batch operations:** 5-15 minutes (transient)
- **Undersized replica:** 30-60 minutes (sustained until upgraded)
- **Network issues:** 5-10 minutes (resolves when AWS fixes network)
- **Typical resolution time:** 15-30 minutes for transient issues

### Storage Growth Patterns
- **Production OLTP databases:** 5-10% monthly growth (steady)
- **Logging/metrics databases:** 15-25% monthly growth (variable)
- **Analytics databases:** 10-15% monthly growth (predictable)
- **Autoscaling trigger:** 90% utilization OR <10GB free space
- **Autoscaling increment:** +50% of current allocated storage (minimum 10GB)

### Configuration Best Practices Validated
1. **Multi-AZ is mandatory for production** (reduces RTO from 60+ min to <5 min)
2. **PITR is mandatory for RPO <1 hour** (reduces RPO from hours to seconds)
3. **Backup retention ≥7 days for production** (compliance and recovery options)
4. **Storage autoscaling must be configured** (prevents outages from growth)
5. **Backup failure monitoring is critical** (silent failures create exposure)
6. **Read replicas must be sized appropriately** (undersized = sustained lag)
7. **Test snapshot restores quarterly** (catch corruption before you need them)
