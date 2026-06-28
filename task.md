# SDET Resume Optimization Tasks

## Security
- [x] Scrub hardcoded credentials from test_ais.py
- [x] Scrub hardcoded credentials from test_ais_flow.py
- [x] Scrub hardcoded credentials from visual_ais_test.py
- [x] Scrub hardcoded credentials from test_run.py
- [x] Scrub hardcoded credentials from main.py
- [x] Scrub hardcoded credentials from test_decrypt.py
- [x] Fix hardcoded internal path in scraper.py (lines 33, 77)
- [x] Create .env.example
- [x] Create root .gitignore

## Test Suite (pytest)
- [x] Create conftest.py (root - sys.path fix)
- [x] Create tests/conftest.py (fixtures)
- [x] Create tests/test_login.py
- [x] Create tests/test_api.py
- [x] Create tests/test_crypto_utils.py
- [x] Create pytest.ini

## CI Pipeline
- [x] Create .github/workflows/ci.yml

## Documentation
- [x] Rewrite README.md

## Code Quality
- [x] Fix bare except → typed PlaywrightTimeout in test files
- [x] Replace time.sleep() → wait_for_timeout() in test files
- [x] Add module docstrings to all test files

## Verification
- [x] 13/13 tests pass (pytest tests/test_crypto_utils.py tests/test_api.py)
- [x] Zero credential leaks in Python files
- [x] Git commit created

## Pending (requires user action)
- [x] Create GitHub repo and push (git remote add origin <url> && git push -u origin main)
- [x] Add IT_PAN, IT_PASSWORD, IT_DOB as GitHub Actions secrets (Settings → Secrets)
- [x] Update CI badge URL in README.md with actual GitHub username/repo
