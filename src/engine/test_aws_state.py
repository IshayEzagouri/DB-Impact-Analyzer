from aws_state import get_fake_db_state

risky_db = get_fake_db_state("prod-orders-db-01")
print("Risky DB Config:")
print(f"  Multi-AZ: {risky_db['multi_az']}")
print(f"  PITR: {risky_db['pitr_enabled']}")
print(f"  Backups: {risky_db['backup_retention_days']} days")
print()

# Test safe database
safe_db = get_fake_db_state("prod-users-db")
print("Safe DB Config:")
print(f"  Multi-AZ: {safe_db['multi_az']}")
print(f"  PITR: {safe_db['pitr_enabled']}")
print(f"  Backups: {safe_db['backup_retention_days']} days")
print()

try:
    get_fake_db_state("nonexistent-db")
except ValueError as e:
    print(f"Error handling works: {e}")
