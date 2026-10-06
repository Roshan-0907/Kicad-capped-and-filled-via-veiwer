"""Toolbar action: make the selected vias (or all vias) filled & capped with solder mask."""

import sys

from pofv import main

sys.exit(main([], mode="apply"))
