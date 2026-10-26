"""Run the measured benchmark without the web UI and optionally export JSON."""
import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))

from app.core.config import get_settings
from app.metrics.evaluation import evaluate


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--include-models',action='store_true')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    result=asyncio.run(evaluate(get_settings(),args.include_models))
    serialized=json.dumps(result,indent=2)
    if args.output:
        if args.output.exists():
            parser.error('Output already exists; choose a new report filename')
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(serialized,encoding='utf-8')
    for system in result['systems']:
        print(f"{system['system']}: {system['correct']}/{system['total']} correct")
    print(result['model_baselines'])


if __name__=='__main__':
    main()
