import boto3
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

def get_real_db_state(db_identifier: str, region: str='us-east-1', profile_name: str=None) -> dict:
    if profile_name:
        session = boto3.Session(profile_name=profile_name)
        rds = session.client('rds', region_name=region)

    else:
        rds = boto3.client('rds', region_name=region)
    response = rds.describe_db_instances(DBInstanceIdentifier=db_identifier)
    db=response['DBInstances'][0]

    return {
        "identifier": db['DBInstanceIdentifier'],
        'instance_class': db['DBInstanceClass'],
        'engine': db['Engine'],
        'multi_az': db['MultiAZ'],
        'backup_retention_days': db['BackupRetentionPeriod'],
        #pitr_enabled is automaticaly enabled if there is a backup retention period
        "pitr_enabled": db['BackupRetentionPeriod'] > 0,

    }

