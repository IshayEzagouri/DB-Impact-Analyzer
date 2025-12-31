import boto3
import json
from prompt_builder import build_prompt
from aws_state import get_fake_db_state
from business_context import load_business_context
from models import DbScenarioRequest, DbImpactResponse

def run_simulation(request: DbScenarioRequest) -> DbImpactResponse:
    db_state = get_fake_db_state(request.db_identifier)
    business_context = load_business_context()
    prompt = build_prompt(request, db_state, business_context)
    raw_response = call_bedrock(prompt)
    parsed= DbImpactResponse.model_validate_json(raw_response)
    return parsed

def call_bedrock(prompt:str) -> str:
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
    bedrock=boto3.client('bedrock-runtime', region_name='us-east-1')
    response = bedrock.invoke_model(
      modelId="anthropic.claude-3-5-sonnet-20241022-v2:0",
      body=body
  )
    response_body = json.loads(response['body'].read())
    return response_body['content'][0]['text']
