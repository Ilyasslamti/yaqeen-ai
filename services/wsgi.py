"""WSGI file for PythonAnywhere — ضع هذا الملف في /home/yourusername/mysite/"""
import sys, os
path = os.path.dirname(os.path.abspath(__file__))
if path not in sys.path: sys.path.insert(0, path)
from webhook_bot import app as application
