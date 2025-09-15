#!/usr/bin/env python3
"""
Wrapper script to run Python AzViz directly from the project directory.

This script allows you to run Python AzViz without installing it:
    python azviz.py export --resource-group my-rg
    python azviz.py list-rg
    python azviz.py --help
"""

import sys
from pathlib import Path

# Add src directory to Python path so we can import azviz
project_root = Path(__file__).parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

# Import and run the CLI
try:
    from azviz.cli import main

    if __name__ == "__main__":
        main()

except ImportError as e:
    print(f"❌ Error importing azviz: {e}")
    print(
        "\n💡 Make sure you're running from the python-azviz directory and have installed dependencies:",
    )
    print("   pip install -r requirements.txt")
    print("   # or")
    print("   pip install -e .")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
