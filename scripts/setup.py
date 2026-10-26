"""Install VEYRA locally; existing databases and configuration are preserved."""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PYTHON=ROOT/'.venv'/('Scripts/python.exe' if sys.platform=='win32' else 'bin/python')


def run(command,cwd=ROOT):
    subprocess.run([str(part) for part in command],cwd=cwd,check=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true',help='Check prerequisites and installed files without installing anything')
    args=parser.parse_args()
    if sys.version_info[:2]!=(3,12):
        parser.error('Use Python 3.12 (Windows: py -3.12 scripts/setup.py)')
    node=shutil.which('node')
    npm=shutil.which('npm.cmd' if sys.platform=='win32' else 'npm')
    if not node or (not args.check and not npm):
        parser.error('Install Node.js 24 LTS, reopen your terminal, and verify node --version and npm --version')
    version=subprocess.check_output([node,'--version'],text=True).strip()
    if int(version.lstrip('v').split('.')[0])<22:
        parser.error('Node.js 22 or newer is required; Node.js 24 is the tested version')
    print(f'Python {sys.version.split()[0]} and Node {version} found',flush=True)
    if args.check:
        required=[PYTHON,ROOT/'frontend/node_modules/vite/bin/vite.js',ROOT/'datasets/veyra.db']
        missing=[str(path.relative_to(ROOT)) for path in required if not path.exists()]
        if missing:
            parser.error('Setup is incomplete: '+', '.join(missing)+'. Run this script without --check.')
        run([PYTHON,'-m','pip','check'])
        run([PYTHON,'-c','import fastapi, uvicorn, sqlglot, scipy, sklearn'])
        print('Local installation checks passed. Ollama is optional.')
        return
    if not PYTHON.exists():
        run([sys.executable,'-m','venv',ROOT/'.venv'])
    run([PYTHON,'-m','pip','install','-r',ROOT/'backend/requirements.lock.txt'])
    run([npm,'exec','--yes','--package=pnpm@11.25.0','--','pnpm','install','--frozen-lockfile'],ROOT/'frontend')
    database=ROOT/'datasets/veyra.db'
    if not database.exists():
        run([PYTHON,ROOT/'scripts/generate_dataset.py'])
    else:
        print('Existing demo database preserved.',flush=True)
    print('Setup complete. Run .venv/Scripts/python.exe scripts/run.py on Windows, or .venv/bin/python scripts/run.py on macOS/Linux.')


if __name__=='__main__':
    try:
        main()
    except subprocess.CalledProcessError as exc:
        print(f'Setup command failed (exit {exc.returncode}). Check the output above, fix the prerequisite or network issue, and rerun setup.',file=sys.stderr)
        sys.exit(exc.returncode)
