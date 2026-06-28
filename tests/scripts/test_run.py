"""
test_run.py — Integration smoke test for the 26AS download pipeline.

Reads credentials from environment variables (see .env.example).
Run with:
    IT_PAN=<pan> IT_PASSWORD=<pwd> IT_DOB=<ddmmyyyy> python test_run.py
"""

import os
from src.scraper import download_26as_for_client
from loguru import logger


def _get_clients_from_env():
    """Build the client list from environment variables."""
    pan = os.environ.get("IT_PAN", "")
    password = os.environ.get("IT_PASSWORD", "")
    dob = os.environ.get("IT_DOB", "")

    if not all([pan, password, dob]):
        raise EnvironmentError(
            "Missing required environment variables: IT_PAN, IT_PASSWORD, IT_DOB. "
            "Copy .env.example to .env and fill in your credentials."
        )

    return [(pan, password, dob, f"test_output/{pan}")]


def test_integration():
    os.makedirs("test_output", exist_ok=True)
    logger.info("Starting integration test for AIS Activity History Edge Case...")

    clients = _get_clients_from_env()

    for pan, pwd, dob, outdir in clients:
        os.makedirs(outdir, exist_ok=True)
        success, msg = download_26as_for_client(pan, pwd, dob, outdir, headless=True)
        logger.info(f"Test Result for {pan}: Success={success}, Message={msg}")


if __name__ == "__main__":
    test_integration()
