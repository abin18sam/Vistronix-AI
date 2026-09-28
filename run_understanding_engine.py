import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
SERVICE_DIR = ROOT

cmd = [
    sys.executable,
    "-m",
    "uvicorn",
    "app.main:app",
    "--host",
    "127.0.0.1",
    "--port",
    "8001",
    "--reload",
]

print(f"Starting understanding engine from: {SERVICE_DIR}")
subprocess.run(cmd, cwd=SERVICE_DIR, check=True)
