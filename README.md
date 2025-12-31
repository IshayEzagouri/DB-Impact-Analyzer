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

## 7. Hardening (Optional But Good)

- Validate Bedrock output strictly (schema)
- Timeouts & error handling
- Logging:
  - Scenario
  - DB id
  - SLA/RTO/RPO flags
  - Severity
- Very basic CloudWatch dashboard (calls per day, error count)

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

