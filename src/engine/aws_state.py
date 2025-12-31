FAKE_DATABASES = {
      "prod-orders-db-01": {
          "identifier": "prod-orders-db-01",
          "multi_az": False,
          "backup_retention_days": 1,
          "pitr_enabled": False,
          "engine": "mysql",
          "instance_class": "db.m5.large"
      },
      "prod-users-db": {
          "identifier": "prod-users-db",
          "multi_az": True,  
          "backup_retention_days": 7,
          "pitr_enabled": True,
          "engine": "postgres",
          "instance_class": "db.m5.xlarge"
      }
}

def get_fake_db_state(db_identifier: str) -> dict:
    """
    Returns fake RDS configuration for Phase 1 testing.
    
    In Phase 2, this will be replaced with real boto3 calls to AWS.
    
    Args:
        db_identifier: RDS database identifier (e.g., "prod-orders-db-01")
    
    Returns:
        dict: Database configuration with keys:
            - identifier, multi_az, backup_retention_days, 
              pitr_enabled, engine, instance_class
    
    Raises:
        ValueError: If db_identifier is not in FAKE_DATABASES
    """
    if db_identifier not in FAKE_DATABASES:
        raise ValueError(f"Database {db_identifier} not found")
    return FAKE_DATABASES[db_identifier]
