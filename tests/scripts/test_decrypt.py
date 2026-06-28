"""
test_decrypt.py — Quick debug script for testing ZIP decryption with different password formats.

The Income Tax portal uses different password conventions depending on the file type.
This script was used to identify the correct decryption key format.

Usage:
    IT_PAN=<pan> IT_DOB=<ddmmyyyy> python test_decrypt.py <path_to_zip>
"""

import sys
import os
import zipfile


def test_zip(zip_path: str, pwd: str):
    """Attempt to extract a password-protected ZIP and report the result."""
    try:
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(path='output/extracted', pwd=pwd.encode('utf-8'))
            print(f"[SUCCESS] Extracted {zip_path} with password format: {pwd[:4]}***")
    except Exception as e:
        print(f"[FAILED]  {zip_path} with this format: {e}")


if __name__ == "__main__":
    zip_path = sys.argv[1] if len(sys.argv) > 1 else "output/sample_text.zip"
    pan = os.environ.get("IT_PAN", "")
    dob = os.environ.get("IT_DOB", "")

    if not pan or not dob:
        print("Usage: IT_PAN=<pan> IT_DOB=<ddmmyyyy> python test_decrypt.py <zip_path>")
        sys.exit(1)

    # Try the three known password formats for TRACES ZIP files
    test_zip(zip_path, dob)
    test_zip(zip_path, pan.lower() + dob)
    test_zip(zip_path, pan.upper() + dob)
