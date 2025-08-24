#!/usr/bin/env python3
"""Simple test runner script for gpt-to-anki tests."""
import subprocess
import sys
import os

def main():
    """Run the test suite with appropriate settings."""
    # Ensure we're in the project root
    project_root = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_root)
    
    # Build the pytest command
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/",
        "-v",  # Verbose output
        "--tb=short",  # Shorter traceback format
        "--asyncio-mode=auto",  # Auto-detect async tests
    ]
    
    # Add any command line arguments passed to this script
    if len(sys.argv) > 1:
        cmd.extend(sys.argv[1:])
    
    print(f"Running: {' '.join(cmd)}")
    print("-" * 50)
    
    # Run the tests
    result = subprocess.run(cmd)
    
    return result.returncode

if __name__ == "__main__":
    sys.exit(main())