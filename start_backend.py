#!/usr/bin/env python
"""
Simple script to start the backend server with correct Python path.
"""
import sys
import os
import subprocess

# Add backend directory to Python path
backend_path = os.path.join(os.path.dirname(__file__), 'backend')
sys.path.insert(0, backend_path)

# Get the Python executable from the virtual environment
venv_python = os.path.join(os.path.dirname(__file__), '.venv', 'Scripts', 'python.exe')

# Run uvicorn using the venv python
if os.path.exists(venv_python):
    subprocess.run([
        venv_python, '-m', 'uvicorn',
        'ap_workflow.main:app',
        '--host', '0.0.0.0',
        '--port', '8000',
        '--reload',
        '--reload-dir', backend_path
    ], cwd=backend_path)
else:
    # Fallback to current python
    import uvicorn
    uvicorn.run(
        'ap_workflow.main:app',
        host='0.0.0.0',
        port=8000,
        reload=True,
        reload_dirs=[backend_path]
    )
