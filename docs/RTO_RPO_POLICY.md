# RTO / RPO Policy

RTO (Recovery Time Objective):
Production database services must be recoverable within 30 minutes of failure.

RPO (Recovery Point Objective):
A maximum of 5 minutes of data loss is acceptable in the event of failure.

Policy Assumptions:
- Automated backups and replication are expected
- DR procedures should be regularly tested