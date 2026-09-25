"""Allow `python -m watson`."""

from watson.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
