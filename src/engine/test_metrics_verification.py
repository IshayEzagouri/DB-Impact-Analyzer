"""
Test script to verify CloudWatch metrics are being called correctly.
This mocks the CloudWatch client to verify metrics without actually sending to AWS.
"""
import sys
from unittest.mock import patch, MagicMock
from src.engine.models import DbImpactResponse, BatchResponse, WhatIfResponse
from src.engine.cloudwatch_metric import emit_analysis_metric, emit_batch_metric, emit_what_if_metric

def test_analysis_metrics():
    """Test that emit_analysis_metric calls CloudWatch with correct data."""
    print("Testing emit_analysis_metric...")
    
    # Create a mock response
    response = DbImpactResponse(
        business_severity="CRITICAL",
        sla_violation=True,
        rto_violation=True,
        rpo_violation=False,
        expected_outage_time_minutes=90,
        why=["Test reason"],
        recommendations=["Test recommendation"],
        confidence=0.85
    )
    
    # Mock the CloudWatch client
    with patch('src.engine.cloudwatch_metric.cloudwatch') as mock_cloudwatch:
        emit_analysis_metric(response, duration_ms=1234.5, scenario="primary_db_failure")
        
        # Verify put_metric_data was called
        assert mock_cloudwatch.put_metric_data.called, "put_metric_data should be called"
        
        # Get the call arguments
        call_args = mock_cloudwatch.put_metric_data.call_args
        namespace = call_args.kwargs['Namespace']
        metric_data = call_args.kwargs['MetricData']
        
        # Verify namespace
        assert namespace == 'DBImpactAgent', f"Expected namespace 'DBImpactAgent', got '{namespace}'"
        
        # Verify we have 5 metrics
        assert len(metric_data) == 5, f"Expected 5 metrics, got {len(metric_data)}"
        
        # Verify AnalysisCount metric
        analysis_count = next(m for m in metric_data if m['MetricName'] == 'AnalysisCount')
        assert analysis_count['Value'] == 1
        assert analysis_count['Unit'] == 'Count'
        assert len(analysis_count['Dimensions']) == 2
        assert analysis_count['Dimensions'][0]['Name'] == 'Severity'
        assert analysis_count['Dimensions'][0]['Value'] == 'CRITICAL'
        
        # Verify AnalysisDuration
        duration = next(m for m in metric_data if m['MetricName'] == 'AnalysisDuration')
        assert duration['Value'] == 1234.5
        assert duration['Unit'] == 'Milliseconds'
        
        # Verify SLAViolationRate
        sla = next(m for m in metric_data if m['MetricName'] == 'SLAViolationRate')
        assert sla['Value'] == 1  # True = 1
        assert sla['Unit'] == 'None'
        
        print("✅ emit_analysis_metric: PASSED")
        print(f"   - Namespace: {namespace}")
        print(f"   - Metrics sent: {len(metric_data)}")
        print(f"   - AnalysisCount dimensions: {analysis_count['Dimensions']}")


def test_batch_metrics():
    """Test that emit_batch_metric calls CloudWatch with correct data."""
    print("\nTesting emit_batch_metric...")
    
    # Create a mock batch response
    batch_response = BatchResponse(
        total_count=3,
        critical_count=1,
        high_count=1,
        medium_count=1,
        low_count=0,
        results=[
            {"status": "success", "analysis": {"sla_violation": True, "rto_violation": False, "rpo_violation": True}},
            {"status": "success", "analysis": {"sla_violation": False, "rto_violation": True, "rpo_violation": False}},
            {"status": "success", "analysis": {"sla_violation": True, "rto_violation": False, "rpo_violation": False}},
        ]
    )
    
    with patch('src.engine.cloudwatch_metric.cloudwatch') as mock_cloudwatch:
        emit_batch_metric(batch_response, duration_ms=5000.0)
        
        assert mock_cloudwatch.put_metric_data.called, "put_metric_data should be called"
        
        call_args = mock_cloudwatch.put_metric_data.call_args
        namespace = call_args.kwargs['Namespace']
        metric_data = call_args.kwargs['MetricData']
        
        assert namespace == 'DBImpactAgent'
        assert len(metric_data) == 10, f"Expected 10 metrics, got {len(metric_data)}"
        
        # Verify BatchSize
        batch_size = next(m for m in metric_data if m['MetricName'] == 'BatchSize')
        assert batch_size['Value'] == 3
        
        # Verify BatchCriticalCount
        critical = next(m for m in metric_data if m['MetricName'] == 'BatchCriticalCount')
        assert critical['Value'] == 1
        
        print("✅ emit_batch_metric: PASSED")
        print(f"   - Metrics sent: {len(metric_data)}")
        print(f"   - BatchSize: {batch_size['Value']}")


def test_what_if_metrics():
    """Test that emit_what_if_metric calls CloudWatch with correct data."""
    print("\nTesting emit_what_if_metric...")
    
    # Create mock what-if response
    baseline = DbImpactResponse(
        business_severity="CRITICAL",
        sla_violation=True,
        rto_violation=True,
        rpo_violation=True,
        expected_outage_time_minutes=120,
        why=["Baseline issue"],
        recommendations=["Baseline fix"],
        confidence=0.9
    )
    
    what_if = DbImpactResponse(
        business_severity="HIGH",
        sla_violation=False,
        rto_violation=False,
        rpo_violation=False,
        expected_outage_time_minutes=60,
        why=["What-if issue"],
        recommendations=["What-if fix"],
        confidence=0.85
    )
    
    what_if_response = WhatIfResponse(
        baseline_analysis=baseline,
        what_if_analysis=what_if,
        improvement_summary={
            "severity_improved": True,
            "severity_change": "CRITICAL -> HIGH",
            "rto_reduction_minutes": 60,
            "sla_violation_prevented": True,
            "rto_violation_prevented": True,
            "rpo_violation_prevented": True
        }
    )
    
    with patch('src.engine.cloudwatch_metric.cloudwatch') as mock_cloudwatch:
        emit_what_if_metric(what_if_response, duration_ms=3000.0, scenario="primary_db_failure")
        
        assert mock_cloudwatch.put_metric_data.called, "put_metric_data should be called"
        
        call_args = mock_cloudwatch.put_metric_data.call_args
        namespace = call_args.kwargs['Namespace']
        metric_data = call_args.kwargs['MetricData']
        
        assert namespace == 'DBImpactAgent'
        assert len(metric_data) == 7, f"Expected 7 metrics, got {len(metric_data)}"
        
        # Verify WhatIfSeverityImproved
        severity_improved = next(m for m in metric_data if m['MetricName'] == 'WhatIfSeverityImproved')
        assert severity_improved['Value'] == 1  # True = 1
        
        # Verify WhatIfRTOReduction
        rto_reduction = next(m for m in metric_data if m['MetricName'] == 'WhatIfRTOReduction')
        assert rto_reduction['Value'] == 60
        
        print("✅ emit_what_if_metric: PASSED")
        print(f"   - Metrics sent: {len(metric_data)}")
        print(f"   - SeverityImproved: {severity_improved['Value']}")


if __name__ == '__main__':
    print("=" * 60)
    print("CloudWatch Metrics Verification Test")
    print("=" * 60)
    
    try:
        test_analysis_metrics()
        test_batch_metrics()
        test_what_if_metrics()
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED - Metrics are being called correctly!")
        print("=" * 60)
        print("\nNote: This test mocks CloudWatch, so no actual metrics were sent.")
        print("To send real metrics, configure AWS credentials and run your app.")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

