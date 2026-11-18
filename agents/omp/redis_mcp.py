#!/usr/bin/env python3
"""
OMP Agent — Redis Mailbox MCP Entry Point
"""

import os
import sys

# Add the mailbox module to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "mailbox"))

from mailbox.mcp_server import main

if __name__ == "__main__":
    main("omp")