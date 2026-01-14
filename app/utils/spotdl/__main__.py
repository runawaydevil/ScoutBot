"""
Main module for spotdl. Exports version and main function.
"""

from app.utils.spotdl._version import __version__
from app.utils.spotdl.console import console_entry_point

if __name__ == "__main__":
    console_entry_point()
