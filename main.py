"""Entry point for the SiMonPro desktop application.

Runs the Desktop P1 interface (src/ui) against the SiMonPro REST API.
Server address: SIMONPRO_API_URL (default http://localhost:8000/api/v1).
Login: an account of the server, e.g. operasional / operasional123 from database/dummy.sql.
Offline demo with the fixed sample data: SIMONPRO_SAMPLE=1 (login operasional / simonpro).
"""

import sys

from src.ui.app import run

if __name__ == "__main__":
    sys.exit(run(sys.argv))
