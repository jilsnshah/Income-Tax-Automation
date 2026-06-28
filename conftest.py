"""
Root conftest.py — ensures the project root is on sys.path so that
`pytest` (called directly, without `python -m pytest`) can import
project modules like `crypto_utils`, `server`, and `scraper`.
"""

import sys
import os

# Add the project root to sys.path
sys.path.insert(0, os.path.dirname(__file__))
