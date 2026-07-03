import os
import sys

# Make the repo-root modules (rules_agent, askscreen_html, …) importable from tests/.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
