"""Compatibility entry point: exports actual input geometry without primitive fallbacks."""
import runpy
from pathlib import Path
runpy.run_path(str(Path(__file__).with_name('export_character.py')), run_name='__main__')
