#!/usr/bin/env python3
"""Launch the Report Agent API server."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from report_agent.api_server import main

main()
