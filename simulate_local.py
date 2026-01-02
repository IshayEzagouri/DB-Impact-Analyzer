import argparse
import sys
from src.engine.models import DbScenarioRequest
from src.engine.reasoning import run_simulation

def main():
    parser = argparse.ArgumentParser(
        description='Simulate a database failure and assess SLA/RTO/RPO impact',
        epilog='Examples:\n  %(prog)s --db prod-orders-db-01\n  %(prog)s --db my-real-rds-db --scenario az_failure',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--db', type=str, required=True,
                       help='Database identifier (fake databases from aws_state.py or real RDS instance)')
    parser.add_argument('--scenario', type=str, required=False, default='primary_db_failure',
                       help='Failure scenario (default: primary_db_failure)')
    args = parser.parse_args()

    try:
        request = DbScenarioRequest(db_identifier=args.db, scenario=args.scenario)
        response = run_simulation(request)
        print(response.model_dump_json(indent=2))
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except PermissionError as e:
        print(f"Permission Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(2)

if __name__ == '__main__':
    main()