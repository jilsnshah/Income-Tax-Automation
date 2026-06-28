import os

# Base paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

# URLs
LOGIN_URL = "https://eportal.incometax.gov.in/iec/foservices/#/login"
DASHBOARD_URL = "https://eportal.incometax.gov.in/iec/foservices/#/dashboard"

# TRACES Constants
ASSESSMENT_YEAR = "2026"

# Playwright settings
TIMEOUT_MS = 180000  # 3 minutes timeout
