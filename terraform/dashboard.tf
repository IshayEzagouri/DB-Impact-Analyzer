# Local variables - single source of truth for scenarios and severities
#
# IMPORTANT: Keep these in sync with the source code!
# - scenarios: Must match keys in src/engine/scenarios.py SCENARIOS dict
# - severities: Must match values used in src/engine/models.py DbImpactResponse
#
# When adding new scenarios:
# 1. Add to src/engine/scenarios.py SCENARIOS dict
# 2. Add entry here in locals.scenarios
# 3. Dashboard will automatically include it in Widget 6
locals {
    # Scenarios from src/engine/scenarios.py - keep in sync!
    scenarios = {
        "primary_db_failure" = "Primary Failure"
        "replica_lag"        = "Replica Lag"
        "backup_failure"     = "Backup Failure"
        "storage_pressure"   = "Storage Pressure"
    }

    # Severity levels - keep in sync with models.py
    severities = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
}

resource "aws_cloudwatch_dashboard" "db_impact_agent_dashboard" {
    dashboard_name="db-impact-agent-dashboard"
    dashboard_body = jsonencode({
        widgets = [
      # Widget 1: Analysis Volume (total count, no dimensions)
      {
        type = "metric"
        properties = {
          metrics = [
            ["DBImpactAgent", "AnalysisCount", { stat = "Sum", label = "Total Analyses" }]
          ]
          period = 300
          region = "us-east-1"
          title  = "Analysis Volume (Last 24 Hours)"
          yAxis = {
            left = { min = 0 }
          }
        }
      },
      # Widget 2: Severity Distribution (pie chart)
      {
        type = "metric"
        properties = {
          metrics = [
            ["DBImpactAgent", "AnalysisCount", "Severity", "CRITICAL", { stat = "Sum", label = "CRITICAL" }],
            [".", ".", ".", "HIGH", { stat = "Sum", label = "HIGH" }],
            [".", ".", ".", "MEDIUM", { stat = "Sum", label = "MEDIUM" }],
            [".", ".", ".", "LOW", { stat = "Sum", label = "LOW" }]
          ]
          period = 300
          region = "us-east-1"
          title  = "Analysis Count by Severity"
          view   = "pie"
        }
      },
      # Widget 3: SLA Violation Rate (percentage)
      {
        type = "metric"
        properties = {
          metrics = [
            ["DBImpactAgent", "SLAViolationRate", { stat = "Average", label = "SLA Violation %" }]
          ]
          period = 300
          region = "us-east-1"
          title  = "SLA Violation Rate"
          yAxis = {
            left = { min = 0, max = 1 }
          }
        }
      },
      # Widget 4: Analysis Duration Percentiles (P50, P95, P99)
      {
        type = "metric"
        properties = {
          metrics = [
            ["DBImpactAgent", "AnalysisDuration", { stat = "p50", label = "P50" }],
            [".", ".", { stat = "p95", label = "P95" }],
            [".", ".", { stat = "p99", label = "P99" }]
          ]
          period = 300
          region = "us-east-1"
          title  = "Analysis Duration (Percentiles)"
          yAxis = {
            left = { label = "Milliseconds" }
          }
        }
      },
      # Widget 5: Lambda Errors & Throttles
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/Lambda", "Errors", "FunctionName", var.function_name, { stat = "Sum", label = "Errors" }],
            [".", "Throttles", ".", ".", { stat = "Sum", label = "Throttles" }]
          ]
          period = 300
          region = "us-east-1"
          title  = "Lambda Errors & Throttles"
        }
      },
      # Widget 6: Scenario Usage (bar chart)
      {
        type = "metric"
        properties = {
          metrics = [
            ["DBImpactAgent", "AnalysisCount", "Scenario", "primary_db_failure", { stat = "Sum", label = "Primary Failure" }],
            [".", ".", ".", "replica_lag", { stat = "Sum", label = "Replica Lag" }],
            [".", ".", ".", "backup_failure", { stat = "Sum", label = "Backup Failure" }],
            [".", ".", ".", "storage_pressure", { stat = "Sum", label = "Storage Pressure" }]
          ]
          period = 300
          region = "us-east-1"
          title  = "Usage by Scenario"
          view   = "bar"
        }
      }

    ]
    })
}
