#!/usr/bin/env python3
"""
fetch_nav.py — placeholder (short-period data not yet available)

All return periods (2025 / 2024 / 2023 / 3Y / 5Y) are now sourced
directly from mpp_list.jsp by fetch_mpfa.py.  This script is kept
for future use when a reliable short-period data source is found.
"""
import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)
log.info("fetch_nav.py: nothing to do (all data from fetch_mpfa.py)")
