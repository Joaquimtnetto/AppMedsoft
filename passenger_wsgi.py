import os
import sys

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
BACKEND_ROOT = os.path.join(APP_ROOT, "backend")

sys.path.insert(0, BACKEND_ROOT)
sys.path.insert(0, APP_ROOT)

from medsoft_app import app as application
