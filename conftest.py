import os
import sys

# Make the repo-root modules (rules_agent, askscreen_html, …) importable from tests/.
_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _root)
# …and the shared test datasets/helpers that live under tests/ (golden_retrieval, …).
sys.path.insert(0, os.path.join(_root, "tests"))
