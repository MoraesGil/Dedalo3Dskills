#!/usr/bin/env python3
"""Repository convenience wrapper. The installed skill contains the canonical tool."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'skills'/'printing'/'torre-burj'/'scripts'))
from burj.cli import main
if __name__=='__main__':raise SystemExit(main())
