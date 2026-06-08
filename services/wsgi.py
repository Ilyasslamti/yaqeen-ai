"""WSGI file for PythonAnywhere"""
import sys, os
path = os.path.dirname(os.path.abspath(__file__))
if path not in sys.path: sys.path.insert(0, path)

# Env vars are set via PythonAnywhere Web → Environment variables
# Do NOT hardcode secrets here — PA panel is the source of truth

from webhook_bot import app as application
