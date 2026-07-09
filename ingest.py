"""Backwards-compatible entry point — logic lives in gsas_query/ingest.py."""
# Must come first: prevents loky/tokenizers from spawning workers (kills on
# Python 3.13 + macOS spawn start method).
import os
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import multiprocessing
from gsas_query.ingest import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
