 # Database Incident History

  ## 2024-03-15: prod-orders-db-01 Failure
  - **Cause:** Hardware failure (AWS-side)
  - **Configuration:** Single-AZ, daily snapshots
  - **Recovery time:** 87 minutes (snapshot restore)
  - **Data loss:** ~18 hours (last backup was from previous night)

  ## 2024-06-22: prod-users-db Failover
  - **Cause:** AZ outage (us-east-1a)
  - **Configuration:** Multi-AZ enabled
  - **Recovery time:** 3 minutes (automatic failover)
  - **Data loss:** None

  ## Key Learnings
  - Snapshot restores to db.m5.large instances average 60-90 minutes
  - Multi-AZ failovers consistently complete in <5 minutes
  - PITR is essential for RPO < 1 hour
