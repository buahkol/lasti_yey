"""Entry point for the SiMonPro desktop application.

Runs the new Desktop P1 interface (src/ui). Data is still hard-coded in
src/ui/mock_data.py until the REST API is connected.
Demo login: operasional / simonpro
"""

import sys

from src.ui.app import run

if __name__ == "__main__":
    sys.exit(run(sys.argv))
