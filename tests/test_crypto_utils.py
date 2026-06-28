"""
tests/test_crypto_utils.py — Unit tests for the PDF/ZIP decryption utilities.

Tests cover:
  - decrypt_pdf: happy path with a real encrypted PDF
  - decrypt_pdf: wrong password returns False (negative test)
  - decrypt_pdf: non-encrypted PDF is a no-op (boundary)
  - decrypt_pdf: non-existent file is handled gracefully (error path)
  - process_client_files: strict cleanup removes unexpected files

No Playwright, no network, no credentials required.
These run in under 1 second and are safe for all CI environments.
"""

import os
import pytest
from unittest.mock import patch

# Attempt to import; skip module if dependencies missing
try:
    from src.crypto_utils import decrypt_pdf, process_client_files
except ImportError as e:
    pytest.skip(f"crypto_utils import failed: {e}", allow_module_level=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_encrypted_pdf(path: str, password: str) -> None:
    """Create a minimal password-protected PDF at the given path."""
    from pypdf import PdfWriter
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.encrypt(password)
    with open(path, "wb") as f:
        writer.write(f)


def _make_plain_pdf(path: str) -> None:
    """Create a minimal unencrypted PDF at the given path."""
    from pypdf import PdfWriter
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    with open(path, "wb") as f:
        writer.write(f)


# ---------------------------------------------------------------------------
# decrypt_pdf tests
# ---------------------------------------------------------------------------

class TestDecryptPdf:
    """Unit tests for decrypt_pdf()."""

    def test_decrypts_valid_encrypted_pdf(self, tmp_path):
        """
        Happy path: encrypted PDF + correct password → file is decrypted in-place,
        function returns True.
        """
        pdf_path = str(tmp_path / "test.pdf")
        _make_encrypted_pdf(pdf_path, "correct_password")

        result = decrypt_pdf(pdf_path, "correct_password")

        assert result is True, "decrypt_pdf should return True on success"
        # Verify the file is now readable without a password
        from pypdf import PdfReader
        reader = PdfReader(pdf_path)
        assert not reader.is_encrypted, "PDF should be decrypted after successful call"

    def test_wrong_password_returns_false(self, tmp_path):
        """
        Negative test: wrong password should return False, not raise.
        Equivalence class: invalid password partition.
        """
        pdf_path = str(tmp_path / "test_wrong.pdf")
        _make_encrypted_pdf(pdf_path, "correct_password")

        result = decrypt_pdf(pdf_path, "wrong_password")

        assert result is False, "decrypt_pdf should return False when password is incorrect"

    def test_unencrypted_pdf_is_noop(self, tmp_path):
        """
        Boundary test: calling decrypt_pdf on an already-unencrypted PDF
        should return True and leave the file intact.
        """
        pdf_path = str(tmp_path / "plain.pdf")
        _make_plain_pdf(pdf_path)
        size_before = os.path.getsize(pdf_path)

        result = decrypt_pdf(pdf_path, "anypassword")

        assert result is True
        assert os.path.getsize(pdf_path) == size_before, (
            "Unencrypted PDF should not be modified"
        )

    def test_nonexistent_file_returns_false(self, tmp_path):
        """
        Error path: non-existent file should not raise an unhandled exception;
        it should return False and log the error gracefully.
        """
        result = decrypt_pdf(str(tmp_path / "does_not_exist.pdf"), "password")
        assert result is False, "decrypt_pdf should return False for a missing file"


# ---------------------------------------------------------------------------
# process_client_files cleanup tests
# ---------------------------------------------------------------------------

class TestProcessClientFilesCleanup:
    """
    Tests for the strict cleanup logic in process_client_files().
    Only the 4 canonical output files should survive; everything else is deleted.
    """

    def test_removes_unexpected_files(self, tmp_path):
        """
        After process_client_files runs, only the 4 canonical files
        (ais, tis, html pdf, text) should remain in the output dir.
        Any extra files (e.g. debug dumps, screenshots) must be removed.
        """
        pan = "TESTPAN123"
        dob = "01012000"
        out = str(tmp_path)

        # Create the 4 allowed files (empty — no real decryption needed)
        allowed = [
            f"{pan}_ais.pdf",
            f"{pan}_tis.pdf",
            f"{pan}_html.pdf",
            f"{pan}_text.txt",
        ]
        for fname in allowed:
            open(os.path.join(out, fname), "w").close()

        # Create an extra file that should be cleaned up
        extra = os.path.join(out, f"{pan}_debug_screenshot.png")
        open(extra, "w").close()

        # Patch the decrypt functions so we don't need real PDFs
        with patch("src.crypto_utils.decrypt_pdf", return_value=True), \
             patch("src.crypto_utils.decrypt_zip", return_value=True):
            process_client_files(pan, dob, out)

        remaining = set(os.listdir(out))
        assert extra.split("/")[-1] not in remaining, (
            "Extra files should be removed by the strict cleanup"
        )
        for fname in allowed:
            assert fname in remaining, f"Allowed file {fname} should remain after cleanup"
