"""Ponto de entrada WSGI usado pelo Phusion Passenger no cPanel."""

import os
import sys


APP_ROOT = os.path.dirname(os.path.abspath(__file__))
BACKEND_ROOT = os.path.join(APP_ROOT, "backend")

if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from medsoft_app import app as application
from email_robot import start_email_robot


start_email_robot(application)
