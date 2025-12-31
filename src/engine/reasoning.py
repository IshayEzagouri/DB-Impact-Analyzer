import boto3
import json
import os
from src.engine.prompt_builder import build_prompt
from src.engine.aws_state import FAKE_DATABASES, get_fake_db_state, get_real_db_state
from src.engine.business_context import load_business_context
from src.engine.models import DbScenarioRequest, DbImpactResponse
IS_LAMBDA = os.getenv('AWS_EXECUTION_ENV') is not None
def run_simulation(request: DbScenarioRequest) -> DbImpactResponse:
    # use fake database if it is in the fake databases list to avoid calling aws and incur costs
    if request.db_identifier in  FAKE_DATABASES:
        db_state = get_fake_db_state(request.db_identifier)
    else:
        profile=None if IS_LAMBDA else 'develeap-ishay'
        db_state = get_real_db_state(request.db_identifier, profile_name=profile)
    business_context = load_business_context()
    prompt = build_prompt(request, db_state, business_context)
    raw_response = call_bedrock(prompt)

    # Extract JSON from response (handle markdown, leading text, etc.)
    cleaned_response = raw_response.strip()

    # Find the JSON object - look for first { and last }
    first_brace = cleaned_response.find('{')
    last_brace = cleaned_response.rfind('}')

    if first_brace != -1 and last_brace != -1:
        # Extract just the JSON portion
        cleaned_response = cleaned_response[first_brace:last_brace + 1]

    parsed = DbImpactResponse.model_validate_json(cleaned_response)
    return parsed

def call_bedrock(prompt: str) -> str:
    """Calls AWS Bedrock to get AI assessment."""

    # ===== ORIGINAL CLAUDE/ANTHROPIC CODE (requires approval) =====
    # body = json.dumps({
    #     "anthropic_version": "bedrock-2023-05-31",
    #     "max_tokens": 2000,
    #     "messages": [
    #         {
    #             "role": "user",
    #             "content": prompt
    #         }
    #     ]
    # })
    # bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
    # response = bedrock.invoke_model(
    #     modelId="anthropic.claude-3-5-sonnet-20240620-v1:0",
    #     body=body
    # )
    # response_body = json.loads(response['body'].read())
    # return response_body['content'][0]['text']
    # ================================================================

    # ===== LLAMA 3 IMPLEMENTATION (no approval needed) =====
    bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')

    # Llama 3 uses a different request format
    body = json.dumps({
        "prompt": prompt,
        "max_gen_len": 2048,
        "temperature": 0.1,  # Low temperature for consistent structured output
        "top_p": 0.9
    })

    response = bedrock.invoke_model(
        modelId="meta.llama3-70b-instruct-v1:0",
        body=body
    )

    response_body = json.loads(response['body'].read())
    return response_body['generation']
