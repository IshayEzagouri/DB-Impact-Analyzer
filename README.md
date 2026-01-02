# DB Failure → SLA/RTO/RPO Impact Agent

## 0. Scope (Narrow, On-Purpose)

**MVP name:** DB Failure → SLA/RTO/RPO Impact Agent

### Input
```json
{
  "db_identifier": "prod-orders-db-01"
}
```

### Output (core fields, ALWAYS present)
```json
{
  "sla_violation": true,
  "rto_violation": true,
  "rpo_violation": true,
  "expected_outage_time_minutes": 90,
  "business_severity": "CRITICAL",
  "why": [
    "No Multi-AZ",
    "Backups only once nightly",
    "RTO policy is 30 minutes, RPO is 5 minutes",
    "Historical restore took ~90 minutes"
  ],
  "recommendations": [
    "Enable Multi-AZ",
    "Enable PITR",
    "Test automated failover"
  ],
  "confidence": 0.86
}
```

**The 5 core questions = first 5 fields. They do not change.**

Everything you code exists to fill these 5 correctly:
1. `sla_violation` - Will we breach our SLA?
2. `rto_violation` - Will we exceed Recovery Time Objective?
3. `rpo_violation` - Will we exceed Recovery Point Objective?
4. `expected_outage_time_minutes` - How long will we be down?
5. `business_severity` - How bad is this?

---

## 1. High-Level Architecture

Keep it simple:

- **Client:** Postman (no UI yet)
- **API:** API Gateway → POST `/simulate-db-failure`
- **Backend:** Lambda (Python)
- **AI:** Bedrock (Claude / whatever)
- **Data sources:**
  - AWS RDS config (via boto3)
  - Business policy docs (SLA/RTO/RPO/Incidents) in S3

### Flow

1. Postman sends:
   ```json
   { "db_identifier": "prod-orders-db-01" }
   ```

2. Lambda:
   - Fetches RDS state
   - Fetches policy docs
   - Builds prompt
   - Calls Bedrock
   - Parses response into fixed schema

3. Returns JSON above.

---

## 2. Repo Layout

```
db-sla-impact-agent/
  src/
    engine/                # AI brain + logic
      models.py            # Pydantic/dataclass models
      aws_state.py         # read RDS config
      business_context.py  # load SLA/RTO/RPO docs
      prompt_builder.py    # build Bedrock prompt
      reasoning.py         # glue everything: run_simulation()
    infra/                 # AWS wrappers
      lambda_handler.py    # API Gateway → Lambda bridge
  docs/                    # local copies of business truth
    SLA.md
    RTO_RPO_POLICY.md
    INCIDENT_HISTORY.md
  config/
    settings.json          # region, S3 bucket names, etc.
  requirements.txt
  README.md
```

---

## 3. Phase 1 – Local Brain (No AWS, No Lambda Yet)

**Goal:** A local Python function that, given a fake DB config + docs, reliably answers the 5 questions.

### 3.1 Define models (`src/engine/models.py`)

**DbScenarioRequest:**
```python
class DbScenarioRequest(BaseModel):
    db_identifier: str
    scenario: str = "primary_db_failure"
```

**DbImpactResponse:**
```python
class DbImpactResponse(BaseModel):
    sla_violation: bool
    rto_violation: bool
    rpo_violation: bool
    expected_outage_time_minutes: int
    business_severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    why: list[str]
    recommendations: list[str]
    confidence: float
```

### 3.2 Fake AWS state (`aws_state.py`)

For now, hardcode:

```python
def get_fake_db_state(db_identifier: str) -> dict:
    return {
        "identifier": db_identifier,
        "multi_az": False,
        "backup_retention_days": 1,
        "pitr_enabled": False,
        "engine": "mysql",
        "instance_class": "db.m5.large"
    }
```

### 3.3 Local business docs (`business_context.py`)

Load text from `docs/*.md`:

```python
def load_business_context() -> str:
    # concat SLA.md + RTO_RPO_POLICY.md + INCIDENT_HISTORY.md
    return combined_text
```

**Example contents:**

**SLA.md:**
```
99.95% monthly availability.
Outage > 30 minutes = SLA breach.
```

**RTO_RPO_POLICY.md:**
```
RTO: 30 minutes.
RPO: 5 minutes.
No permanent data loss allowed for orders DB.
```

### 3.4 Prompt builder (`prompt_builder.py`)

Build a single clear prompt:
- Explain the 5 questions explicitly.
- Give the RDS config summary.
- Give business docs.
- Instruct the model to output ONLY JSON in the `DbImpactResponse` shape.

### 3.5 Reasoning glue (`reasoning.py`)

```python
def run_simulation(req: DbScenarioRequest) -> DbImpactResponse:
    db_state = get_fake_db_state(req.db_identifier)
    business_text = load_business_context()
    prompt = build_prompt(req, db_state, business_text)
    raw = call_bedrock(prompt)      # you'll write this
    parsed = DbImpactResponse.parse_raw(raw)
    return parsed
```

### 3.6 CLI runner

`simulate_local.py`:

```bash
python simulate_local.py --db prod-orders-db-01
```

Print the JSON.

**Phase 1 done when:**
- You run a couple of test DB configs (e.g. Multi-AZ true vs false).
- The 5 core fields change sensibly.
- `why` + `recommendations` sound consistent.

⏱ **Rough: 4–6 sessions of ~2 hours.**

---

## 4. Phase 2 – Swap Fake AWS for Real RDS (Still Local)

**Goal:** `aws_state.py` stops lying and pulls real config.

### 4.1 Implement real `get_db_state` with boto3

- `describe_db_instances`
- Extract:
  - MultiAZ
  - Backup retention days
  - Engine
  - Instance class
  - Maybe snapshots count

### 4.2 Update `run_simulation` to call real `get_db_state()`

Now your local script uses live AWS truth.

**Phase 2 done when:**
- Change Multi-AZ / backups on the DB → run script → different SLA/RTO/RPO verdict.

⏱ **~2–3 sessions.**

---

## 4.5 Usage / Testing (IMPORTANT - Cost Control)

### Safe Database Names (Free Tier)

**To avoid AWS costs, only use these database identifiers:**

1. **`prod-orders-db-01`** (fake database)
   - Risky config: No Multi-AZ, 1-day backups, no PITR
   - Fast, free, works offline
   - Use for testing high-risk scenarios

2. **`prod-users-db`** (fake database)
   - Safe config: Multi-AZ enabled, 7-day backups, PITR enabled
   - Fast, free, works offline
   - Use for testing low-risk scenarios

3. **`test-db-phase2`** (real RDS instance)
   - **Your only free-tier database**
   - Uses real AWS boto3 calls
   - Validates Phase 2 integration works

### CLI Usage Examples

```bash
# Test with fake risky database (fast, free)
python3 simulate_local.py --db prod-orders-db-01

# Test with fake safe database (fast, free)
python3 simulate_local.py --db prod-users-db

# Test with real RDS database (proves boto3 works)
python3 simulate_local.py --db test-db-phase2

# Custom scenario
python3 simulate_local.py --db prod-orders-db-01 --scenario az_failure
```

### ⚠️ Cost Warning

**DO NOT** use other database names unless they exist in your AWS account. The system will attempt to call `describe_db_instances` which may:
- Fail with an error if the database doesn't exist
- Incur costs if you create additional RDS instances (only 1 free tier allowed)

**Free tier limit**: 1 db.t4g.micro/db.t3.micro/db.t2.micro instance per month

---

## 5. Phase 3 – Turn It Into Lambda + API Gateway

**Goal:** Same brain, now behind an HTTP endpoint so you can show it off.

### 5.1 `lambda_handler.py` (`src/infra/`)

```python
from engine.models import DbScenarioRequest
from engine.reasoning import run_simulation

def handler(event, context):
    body = json.loads(event["body"])
    req = DbScenarioRequest(**body)
    resp = run_simulation(req)
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": resp.json()
    }
```

### 5.2 Infra (you can do by hand or TF later)

**Lambda:**
- **Role:**
  - `rds:DescribeDBInstances` (read-only)
  - `bedrock:InvokeModel`
  - `logs:*`
  - `s3:GetObject` (for Phase 4)

**API Gateway:** POST `/simulate-db-failure` → Lambda proxy integration.

### 5.3 Test with Postman

```
POST https://.../prod/simulate-db-failure
```

**Body:**
```json
{
  "db_identifier": "prod-orders-db-01",
  "scenario": "primary_db_failure"
}
```

You should get the JSON with the 5 fields at the top.

**Phase 3 done when:**
- You can hit it from Postman
- Change DB config in AWS → see impact in the 5 answers

⏱ **~1 week.**

---

## 6. Phase 4 – Move Business Docs to S3 (Simple RAG-ish)

**Goal:** Business truth is no longer baked into code; lives in S3.

### 6.1 Upload your `SLA.md`, `RTO_RPO_POLICY.md`, `INCIDENT_HISTORY.md` to S3

Bucket e.g. `db-sla-agent-config`.

### 6.2 Update `business_context.py`

Instead of reading local files → `s3.get_object()` + concat text.

Now when someone edits SLA or RTO/RPO in S3, your answers change automatically.

**Phase 4 done when:**
- You change SLA in S3 (e.g. allow 60 min outage instead of 30)
- Same DB config now results in different `sla_violation` / `business_severity`.

⏱ **2–3 sessions.**

---

## 7. Phase 5 – Hardening (Production Readiness)

**Goal:** Make the system resilient to failures, easy to debug in production, and safe from bad inputs.

**Current state:** Works perfectly in the happy path. Crashes or hangs when things go wrong.

**Target state:** Handles failures gracefully, has visibility into what's happening, and fails fast with clear error messages.

### What Is Hardening?

Right now your system is like a car that only works on sunny days on smooth roads. Hardening is adding:
- **Seatbelts** (error handling) - don't crash when something goes wrong
- **Dashboard** (logging/monitoring) - see what's happening under the hood
- **Speed limits** (timeouts) - don't wait forever for broken things
- **Guardrails** (input validation) - reject garbage before it causes problems

### Current State Analysis

**✅ What You Already Have:**
1. Pydantic validation - Models validate types automatically
2. Generic exception handler in `lambda_handler.py:20-26`
3. Basic logging - 3 log statements in lambda_handler
4. JSON extraction - Handles Bedrock returning markdown in `reasoning.py:21-29`
5. Fake DB fallback - Avoids AWS costs for test databases

**❌ What's Missing (Phase 5 Will Fix):**
1. No timeouts - RDS/S3/Bedrock calls can hang for 60+ seconds
2. No AWS-specific error handling - "Database not found" crashes instead of returning clear error
3. No retry logic - Transient S3/Bedrock errors = instant failure
4. Minimal logging - Can't debug production issues
5. No input validation - Empty db_identifier accepted, could inject weird characters
6. No performance tracking - Don't know if Bedrock is slow or RDS is slow
7. No custom metrics - Can't see error rates or severity distribution in CloudWatch

### Phase 5 Breakdown

#### 5.1 - Add Timeouts to All AWS Calls

**Why:** Without timeouts, a stuck RDS call makes your Lambda hang for 60 seconds, then timeout, wasting money and making users wait.

**Lambda timeout (30s in Terraform) vs Boto3 timeouts:**
- **Lambda timeout:** Total execution time for entire function (emergency brake)
- **Boto3 timeouts:** Individual service calls (speed limit for each step)
- **Why both:** Boto3 timeouts help you fail fast (5s) with clear errors instead of hitting Lambda's 30s timeout

**What to do:**
```python
from botocore.config import Config

config = Config(
    connect_timeout=5,  # 5 seconds to establish connection
    read_timeout=10     # 10 seconds to read response
)
rds = boto3.client('rds', config=config)
```

**Files to modify:** `aws_state.py`, `business_context.py`, `reasoning.py`

#### 5.2 - Handle AWS-Specific Errors Gracefully

**Why:** When a database doesn't exist, boto3 raises `ClientError` with code `DBInstanceNotFound`. Users should get clear errors, not crashes.

**What to do:**
```python
from botocore.exceptions import ClientError

try:
    response = rds.describe_db_instances(DBInstanceIdentifier=db_identifier)
except ClientError as e:
    error_code = e.response['Error']['Code']
    if error_code == 'DBInstanceNotFound':
        raise ValueError(f"Database '{db_identifier}' not found in AWS")
    elif error_code == 'AccessDenied':
        raise PermissionError(f"No permission to access database '{db_identifier}'")
    else:
        raise
```

**Files to modify:** `aws_state.py`, `business_context.py`, `reasoning.py`

#### 5.3 - Add Retry Logic for Transient Failures

**Why:** S3 and Bedrock sometimes return temporary errors. A simple retry often fixes it.

**What to do:**
```python
config = Config(
    retries={
        'max_attempts': 3,
        'mode': 'standard'  # Uses exponential backoff
    }
)
```

**Files to modify:** `business_context.py`, `reasoning.py`

#### 5.4 - Add Structured Logging Throughout

**Why:** When something breaks at 2am, you need to quickly see which database was queried, what the verdict was, how long each step took.

**What to do:**
```python
logger.info(f"Starting simulation for db={request.db_identifier}, scenario={request.scenario}")
logger.info(f"DB state fetch: {elapsed_ms:.0f}ms")
logger.info(f"Bedrock inference: {elapsed_ms:.0f}ms")
logger.info(f"Simulation complete - severity={response.business_severity}, sla_violation={response.sla_violation}")
```

**Files to modify:** `reasoning.py`, `lambda_handler.py`

#### 5.5 - Add Input Validation

**Why:** Users could send empty strings or malicious input. Fail fast with clear errors.

**What to do:**
```python
from pydantic import BaseModel, field_validator
import re

class DbScenarioRequest(BaseModel):
    db_identifier: str
    scenario: str = "primary_db_failure"

    @field_validator('db_identifier')
    def validate_db_identifier(cls, v):
        if not v or not v.strip():
            raise ValueError("db_identifier cannot be empty")
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9-]{0,62}$', v):
            raise ValueError("db_identifier must be valid AWS RDS identifier")
        return v.strip()
```

**Files to modify:** `models.py`

#### 5.6 - Add Explicit Bedrock Validation Error Handling

**What to do:**
```python
from pydantic import ValidationError

try:
    parsed = DbImpactResponse.model_validate_json(cleaned_response)
except ValidationError as e:
    logger.error(f"Bedrock returned invalid schema: {e.errors()}")
    logger.error(f"Raw Bedrock response: {raw_response[:500]}")
    raise ValueError(f"AI model returned invalid response format")
```

**Files to modify:** `reasoning.py`

#### 5.7 - Add Error Handling to simulate_local.py

**What to do:**
```python
import sys

try:
    # ... existing code ...
except ValueError as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"Unexpected error: {e}", file=sys.stderr)
    sys.exit(2)
```

**Files to modify:** `simulate_local.py`

#### 5.8 - Add Performance Tracking

**What to do:** Time each major step and log durations to identify bottlenecks.

**Files to modify:** `reasoning.py`

#### 5.9 - Add Custom CloudWatch Metrics (Optional)

**What to do:** Publish custom metrics for severity distribution, violation rates, errors.

**Files to modify:** `lambda_handler.py`

### Implementation Priority

**High Priority (Must Do):**
1. 5.1 - Timeouts on AWS calls
2. 5.2 - AWS-specific error handling
3. 5.4 - Structured logging
4. 5.5 - Input validation
5. 5.7 - Error handling in simulate_local.py

**Medium Priority (Should Do):**
6. 5.3 - Retry logic
7. 5.6 - Bedrock validation error handling
8. 5.8 - Performance tracking

**Low Priority (Nice to Have):**
9. 5.9 - CloudWatch custom metrics

### Phase 5 Done When:

1. ✅ All boto3 clients have timeouts
2. ✅ Database not found returns clear error (not crash)
3. ✅ Logs show timing for each step
4. ✅ Empty db_identifier is rejected with clear message
5. ✅ simulate_local.py prints friendly errors
6. ✅ Can see in CloudWatch logs exactly what happened in each request

### Testing Your Hardening

1. **Timeout test:** Temporarily set timeout to 1ms, verify it fails fast
2. **Bad DB test:** `--db nonexistent-database-xyz` → should get clear error
3. **Empty input test:** `--db ""` → should get validation error
4. **S3 error test:** Remove S3 permissions temporarily → should get clear error
5. **Performance test:** Check logs to see timing for each step

⏱ **Rough: 3–4 sessions.**

---

## 8. Reality Check: Does This Actually Revolve Around The 5 Questions?

**Yes:**

Everything we're doing is just:
- **Pull config** → to answer:
  - How fast can we recover?
  - How much data can we lose?
- **Pull policies** → to answer:
  - What are we allowed to lose / how long can we be down?
- **Call AI** → to:
  - Combine the two
  - Compute:
    - SLA violation?
    - RTO violated?
    - RPO violated?
    - Realistic downtime?
    - Severity?

**No other bullshit. No charts. No generic "AI assistant".**

Just:

**DB failure → will we fuck our SLA/RTO/RPO or not? And what should we fix?**

That's the core.

---

## 9. What To Do Next (Concrete)

**Next coding session:**

1. Create repo + folders as above.
2. Implement `DbScenarioRequest` + `DbImpactResponse`.
3. Hardcode fake `get_db_state`.
4. Hardcode docs in `/docs`.
5. Implement very dumb prompt builder and `run_simulation`.
6. Call Bedrock once, inspect result, adjust prompt until you get the right JSON.

Once that works locally, the rest is just wiring.

---

## Summary

**The 5 questions are the backbone. Everything else is just plumbing to answer them in a grounded way.**

This plan locks that in and builds everything around them.

