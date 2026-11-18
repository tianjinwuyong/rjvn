"""ICT-specific entry point for the Unified Station Agent."""
from unified_station import main
import sys

if __name__ == "__main__":
    # Keep ICT as the default even when flags (for example
    # --launch-legacy-ui) are supplied without an explicit station.
    if not any(not arg.startswith("-") for arg in sys.argv[1:]):
        sys.argv.insert(1, "manu_ict")
    raise SystemExit(main())
