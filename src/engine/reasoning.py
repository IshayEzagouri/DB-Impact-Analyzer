import boto3
from botocore.config import Config
from botocore.exceptions import ClientError 
import logging
import time
import json
import os
from src.engine.prompt_builder import build_prompt
from src.engine.aws_state import FAKE_DATABASES, get_fake_db_state, get_real_db_state
from src.engine.business_context import load_business_context
from src.engine.models import DbScenarioRequest, DbImpactResponse, DbConfig

logger = logging.getLogger(__name__)
IS_LAMBDA = os.getenv('AWS_EXECUTION_ENV') is not None
def run_simulation(request: DbScenarioRequest, db_state: DbConfig | None = None, is_what_if: bool = False, baseline_config: DbConfig | None = None) -> DbImpactResponse:
    start_time = time.time()
    logger.info(f"Starting simulation for db={request.db_identifier}, scenario={request.scenario}")
    # use fake database if it is in the fake databases list to avoid calling aws and incur costs
    db_start = time.time()
    if db_state is None:
        if request.db_identifier in  FAKE_DATABASES:
            db_state = get_fake_db_state(request.db_identifier)
        else:
            profile=None if IS_LAMBDA else 'develeap-ishay'
            db_state = get_real_db_state(request.db_identifier, profile_name=profile)
        logger.info(f"DB state fetch: {(time.time() - db_start) * 1000:.0f}ms")
    else:
        logger.info(f"Using provided DB state (skipped fetch)")
    context_start = time.time()
    business_context = load_business_context()
    logger.info(f"Business context fetch: {(time.time() - context_start) * 1000:.0f}ms")
    prompt = build_prompt(request, db_state, business_context, is_what_if=is_what_if, baseline_config=baseline_config)
    bedrock_start = time.time()
    raw_response = call_bedrock(prompt)
    logger.info(f"Bedrock inference: {(time.time() - bedrock_start) * 1000:.0f}ms")

    # Extract JSON from response (handle markdown, leading text, etc.)
    cleaned_response = raw_response.strip()

    # Find the JSON object - look for first { and last }
    first_brace = cleaned_response.find('{')
    last_brace = cleaned_response.rfind('}')

    if first_brace != -1 and last_brace != -1:
        # Extract just the JSON portion
        cleaned_response = cleaned_response[first_brace:last_brace + 1]

    parsed = DbImpactResponse.model_validate_json(cleaned_response)
    total_time = (time.time() - start_time) * 1000
    logger.info(f"Simulation complete in {total_time:.0f}ms - severity={parsed.business_severity}, sla_violation={parsed.sla_violation}")
    
    return parsed

def call_bedrock(prompt: str) -> str:
    """Calls AWS Bedrock to get AI assessment."""

    # ===== CLAUDE/ANTHROPIC CODE =====
    model_id = "anthropic.claude-3-5-sonnet-20240620-v1:0"
    logger.info(f"Using Bedrock model: {model_id}")
    
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 2000,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ]
    })
    config = Config(
        connect_timeout=5,
        read_timeout=30   
    )
    bedrock = boto3.client('bedrock-runtime', region_name='us-east-1', config=config)
    try:
        response = bedrock.invoke_model(
            modelId=model_id,
            body=body
        )
        response_body = json.loads(response['body'].read())
        return response_body['content'][0]['text']
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'AccessDenied':
            raise PermissionError(f"No permission to access bedrock")
        elif error_code == 'ThrottlingException':
            raise ValueError(f"Throttling exception from bedrock - too many requests")
        elif error_code == 'ModelNotFoundException':
            raise ValueError(f"Model not found or not accessible")
        else:
            raise
    # ================================================================

    # ===== LLAMA 3 IMPLEMENTATION (backup - commented out) =====
    # config = Config(
    #     connect_timeout=5,
    #     read_timeout=20   
    # )
    # bedrock = boto3.client('bedrock-runtime', region_name='us-east-1', config=config)
    #
    # # Llama 3 uses a different request format
    # body = json.dumps({
    #     "prompt": prompt,
    #     "max_gen_len": 2048,
    #     "temperature": 0.1,  # Low temperature for consistent structured output
    #     "top_p": 0.9
    # })
    # try:
    #     response = bedrock.invoke_model(
    #         modelId="meta.llama3-70b-instruct-v1:0",
    #         body=body
    #     )
    #     response_body = json.loads(response['body'].read())
    #     return response_body['generation']
    # except ClientError as e:
    #     error_code = e.response['Error']['Code']
    #     if error_code == 'AccessDenied':
    #         raise PermissionError(f"No permission to access bedrock")
    #     elif error_code == 'ThrottlingException':
    #         raise ValueError(f"Throttling exception from bedrock - too many requests")
    #     elif error_code == 'ModelNotFoundException':
    #         raise ValueError(f"Model not found or not accessible")
    #     else:
    #         raise

