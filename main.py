"""
main.py — CLI entry point for single-run batch processing.

Reads credentials from environment variables (IT_PAN, IT_PASSWORD, IT_DOB).
For bulk processing via GUI, start the FastAPI server instead:
    python -m src.server
"""

from src.utils import setup_logging, ensure_output_dir
from src.scraper import download_26as_for_client
from loguru import logger
import os


def main():
    setup_logging()
    ensure_output_dir()

    # Load credentials from environment variables.
    # In production, read from a CSV or encrypted database instead.
    pan = os.environ.get("IT_PAN", "")
    password = os.environ.get("IT_PASSWORD", "")
    dob = os.environ.get("IT_DOB", "")

    if not all([pan, password, dob]):
        logger.error(
            "Missing required environment variables: IT_PAN, IT_PASSWORD, IT_DOB. "
            "See .env.example for instructions."
        )
        return

    clients = [
        {
            "pan": pan,
            "password": password,
            "dob": dob,
        }
    ]

    success_count = 0
    failure_count = 0

    logger.info(f"Starting batch processing for {len(clients)} clients...")

    for client in clients:
        success = download_26as_for_client(client["pan"], client["password"], client["dob"])

        if success:
            success_count += 1
        else:
            failure_count += 1

    logger.info(f"Batch processing completed. Success: {success_count}, Failures: {failure_count}")


if __name__ == "__main__":
    main()
