#!/usr/bin/env python3
"""Backward-compatible alias for the old week-only staging mirror workflow."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from importlib.machinery import SourceFileLoader
mirror=SourceFileLoader("jra_stage_baseline_v2",str(Path(__file__).resolve().parent/"staging-baseline-v2.py")).load_module()
mirror.sync(check="--check" in sys.argv,only="this-week.html")
