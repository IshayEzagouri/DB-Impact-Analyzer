import boto3
from botocore.exceptions import ClientError
from botocore.config import Config
FAKE_DATABASES = {
      "prod-orders-db-01": {
          "identifier": "prod-orders-db-01",
          "multi_az": False,
          "backup_retention_days": 7,
          "pitr_enabled": False,
          "engine": "mysql",
          "instance_class": "db.m5.large",
          "read_replicas": [],
          "allocated_storage": 100,
          "max_allocated_storage": 1000
      },
      "prod-users-db": {
          "identifier": "prod-users-db",
          "multi_az": True,  
          "backup_retention_days": 7,
          "pitr_enabled": True,
          "engine": "postgres",
          "instance_class": "db.m5.xlarge",
          "read_replicas": [],
          "allocated_storage": 100,
          "max_allocated_storage": 1000
      },
        "dev-analytics-db-03": {
      "identifier": "dev-analytics-db-03",
      "multi_az": False,
      "backup_retention_days": 3,
      "pitr_enabled": False,
      "engine": "postgres",
      "instance_class": "db.t3.medium",
      "read_replicas": [],
      "allocated_storage": 450,  # 90% of 500 = storage pressure scenario!
      "max_allocated_storage": 500
  },
  "prod-payments-db": {
      "identifier": "prod-payments-db",
      "multi_az": True,
      "backup_retention_days": 14,
      "pitr_enabled": True,
      "engine": "mysql",
      "instance_class": "db.m5.large",
      "read_replicas": ["prod-payments-db-replica-1", "prod-payments-db-replica-2"],  # For replica_lag testing
      "allocated_storage": 200,
      "max_allocated_storage": 2000
  }
}

def get_fake_db_state(db_identifier: str) -> dict:
    if db_identifier not in FAKE_DATABASES:
        raise ValueError(f"Database {db_identifier} not found")
    return FAKE_DATABASES[db_identifier]

def get_real_db_state(db_identifier: str, region: str='us-east-1', profile_name: str=None) -> dict:
    config = Config(
        connect_timeout=5,
        read_timeout=10   
    )
    if profile_name:
        session = boto3.Session(profile_name=profile_name)
        rds = session.client('rds', region_name=region, config=config)

    else:
        rds = boto3.client('rds', region_name=region, config=config)
        
    try:
        response = rds.describe_db_instances(DBInstanceIdentifier=db_identifier)
        db=response['DBInstances'][0]
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'DBInstanceNotFound':
            raise ValueError(f"Database {db_identifier} not found in AWS")
        elif error_code == 'AccessDenied':
            raise PermissionError(f"No permission to access database {db_identifier}")
        else:
            raise 
    return {
        "identifier": db['DBInstanceIdentifier'],
        'instance_class': db['DBInstanceClass'],
        'engine': db['Engine'],
        'multi_az': db['MultiAZ'],
        'backup_retention_days': db['BackupRetentionPeriod'],
        #pitr_enabled is automaticaly enabled if there is a backup retention period
        "pitr_enabled": db['BackupRetentionPeriod'] > 0,
        "read_replicas": db.get('ReadReplicaDBInstanceIdentifiers', []),
        "allocated_storage": db['AllocatedStorage'],
        "max_allocated_storage": db.get('MaxAllocatedStorage', db['AllocatedStorage']),

    }

