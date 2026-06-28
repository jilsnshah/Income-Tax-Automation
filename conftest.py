"""
Root conftest.py — ensures the project root is on sys.path so that
`pytest` (called directly, without `python -m pytest`) can import
project modules under src/ (e.g. `from src.scraper import ...`).
"""

import sys
import os

# Add the project root to sys.path (parent of this file)
sys.path.insert(0, os.path.dirname(__file__))
