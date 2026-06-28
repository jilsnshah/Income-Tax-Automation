import os
from loguru import logger
from src.config import OUTPUT_DIR

def setup_logging():
    # Setup loguru to output to console and file
    logger.add("run.log", rotation="10 MB", level="INFO")
    
def ensure_output_dir():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        logger.info(f"Created output directory at {OUTPUT_DIR}")

def get_html_filename(pan: str) -> str:
    return os.path.join(OUTPUT_DIR, f"{pan}_html.html")

def get_text_filename(pan: str) -> str:
    return os.path.join(OUTPUT_DIR, f"{pan}_txt.txt")
