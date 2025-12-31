import os

def load_business_context() -> str:
    base = os.path.dirname(__file__)
    docs = os.path.join(base, "..", "..", "docs")

    with open(os.path.join(docs, "SLA.md")) as f:
        sla = f.read()

    with open(os.path.join(docs, "RTO_RPO_POLICY.md")) as f:
        rto_rpo = f.read()
        
    with open(os.path.join(docs, "INCIDENT_HISTORY.md")) as f:
        incidents = f.read()

    return sla + "\n---\n" + rto_rpo + "\n---\n"