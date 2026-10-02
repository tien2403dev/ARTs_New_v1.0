"""Optional command line entry for the same import service (no scheduler included)."""
import argparse
from dataclasses import asdict
import json
from main import configure_logging

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--database',required=True)
    parser.add_argument('--folder',required=True)
    parser.add_argument('--from',dest='date_from',required=True,help='YYYY-MM-DD')
    parser.add_argument('--to',dest='date_to',required=True,help='YYYY-MM-DD')
    args = parser.parse_args()
    configure_logging()
    from services.import_service import ImportService
    result = ImportService(args.database).import_folder(args.folder,args.date_from,args.date_to,print)
    print(json.dumps(asdict(result),ensure_ascii=False,indent=2))

if __name__ == '__main__':
    main()
