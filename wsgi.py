# wsgi.py
import sys
import os

# Sett riktig path til prosjektet
project_home = os.path.join(os.path.dirname(__file__))
if project_home not in sys.path:
    sys.path.insert(0, project_home)

from server import create_app
application = create_app()
