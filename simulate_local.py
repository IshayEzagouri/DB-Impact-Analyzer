import argparse
from src.engine.models import DbScenarioRequest
from src.engine.reasoning import run_simulation

def main():
    parser = argparse.ArgumentParser(description='Simulate a database failure')
    parser.add_argument('--db', type=str, required=True, help='Database identifier')
    parser.add_argument('--scenario', type=str, required=False, default='primary_db_failure', help='Scenario')
    args = parser.parse_args()
    request = DbScenarioRequest(db_identifier=args.db, scenario=args.scenario)
    response = run_simulation(request)
    print(response.model_dump_json(indent=2))

if __name__ == '__main__':
    main()