import os
import boto3

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
        s3 = boto3.client("s3")
        for file in files:
            obj = s3.get_object(Bucket=bucket_name, Key=file)
            content=obj["Body"].read().decode("utf-8")
            content_list.append(content)
    return "\n---\n".join(content_list)