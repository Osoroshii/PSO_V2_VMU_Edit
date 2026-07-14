import os
import sys

# Make android/ itself importable (session.py, vmu_scan.py, storage.py,
# fileio.py, and the psovmu/ symlink all live there as top-level modules,
# not a package) -- same pattern the root tests/ suite uses for the repo root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
