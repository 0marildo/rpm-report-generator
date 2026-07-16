#!/usr/bin/env python3
"""Launch the Fire Safety Technical Report Generator."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from report_agent.ui.app import main

main()
