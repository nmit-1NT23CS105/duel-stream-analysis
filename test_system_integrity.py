"""
Dual-Stream Safety System - Root Test Runner
Dispatches to tests/test_system_integrity.py
"""
import sys
from pathlib import Path

# Add project root to path
root_dir = Path(__file__).resolve().parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from tests.test_system_integrity import run_all_verification_checks

if __name__ == "__main__":
    success = run_all_verification_checks()
    sys.exit(0 if success else 1)
