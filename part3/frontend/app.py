"""
SIH26047 — MediKiosk Frontend Entry Point
"""
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Import main controller from root app
from app import main

if __name__ == "__main__":
    main()
