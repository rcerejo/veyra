"""Run both local development servers; Ctrl+C stops processes started here."""
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    python=ROOT/'.venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    vite=ROOT/'frontend/node_modules/vite/bin/vite.js'
    node=shutil.which('node')
    if not python.exists() or not vite.exists() or not node:
        raise RuntimeError('Run scripts/setup.py first. Node.js must be available on PATH.')
    for port in (8000,5173):
        with socket.socket() as probe:
            try:
                probe.bind(('127.0.0.1',port))
            except OSError as exc:
                raise RuntimeError(f'Port {port} is already occupied. Stop the existing service before running VEYRA.') from exc
    options={'creationflags':subprocess.CREATE_NEW_PROCESS_GROUP} if os.name=='nt' else {'start_new_session':True}
    processes=[]
    try:
        processes.append(subprocess.Popen([str(python),'-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000'],cwd=ROOT/'backend',**options))
        processes.append(subprocess.Popen([node,str(vite),'--host','127.0.0.1','--port','5173','--strictPort'],cwd=ROOT/'frontend',**options))
        print('Starting VEYRA…',flush=True)
        deadline=time.monotonic()+45
        while True:
            if not all(process.poll() is None for process in processes):
                raise RuntimeError('A server exited during startup. Check its output above.')
            try:
                with urllib.request.urlopen('http://127.0.0.1:8000/readyz',timeout=1) as backend:
                    backend_ready=backend.status==200
                with urllib.request.urlopen('http://127.0.0.1:5173/',timeout=1) as frontend:
                    frontend_ready=frontend.status==200
                if backend_ready and frontend_ready:
                    break
            except (urllib.error.URLError,TimeoutError,OSError):
                pass
            if time.monotonic()>deadline:
                raise RuntimeError('Servers did not become ready in 45 seconds. Check setup, the database, and the server output.')
            time.sleep(.25)
        print('VEYRA is ready at http://127.0.0.1:5173/ — Ctrl+C stops both servers.',flush=True)
        while all(process.poll() is None for process in processes):
            time.sleep(.25)
        raise RuntimeError('A server exited. Check its output above; both services will be stopped.')
    except KeyboardInterrupt:
        print('\nStopping VEYRA…',flush=True)
    finally:
        for process in processes:
            if process.poll() is None:
                if os.name=='nt':
                    process.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    os.killpg(process.pid,signal.SIGTERM)
        for process in processes:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


if __name__=='__main__':
    try:
        main()
    except RuntimeError as exc:
        print(str(exc),file=sys.stderr)
        sys.exit(1)
