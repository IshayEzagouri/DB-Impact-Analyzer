import os
import boto3
from botocore.exceptions import ClientError
from botocore.config import Config
def load_business_context() -> str:
    bucket_name = os.getenv("S3_BUCKET_NAME")
    files = ["SLA.md", "RTO_RPO_POLICY.md", "INCIDENT_HISTORY.md"]
    content_list = []
    if bucket_name is None:
        base = os.path.dirname(__file__)
        docs = os.path.join(base, "..", "..", "docs")
        for file in files:
            with open(os.path.join(docs, file)) as f:
                content=f.read()
                content_list.append(content)
    else:
        config = Config(
            connect_timeout=5,  
            read_timeout=10   
        )
        s3 = boto3.client("s3", config=config)
        for file in files:
            try:
                obj = s3.get_object(Bucket=bucket_name, Key=file)
                content = obj["Body"].read().decode("utf-8")
                content_list.append(content)
            except ClientError as e:
                error_code = e.response['Error']['Code']
                if error_code == 'NoSuchBucket':
                    raise ValueError(f"Bucket {bucket_name} not found in AWS")
                elif error_code == 'AccessDenied':
                    raise PermissionError(f"No permission to access bucket {bucket_name}")
                elif error_code == 'NoSuchKey':
                    raise ValueError(f"File {file} not found in bucket {bucket_name}")
                else:
                    raise
    return "\n---\n".join(content_list)