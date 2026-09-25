"""CLI: python -m switchboard.simulator --base-url http://localhost:8000"""

import argparse
import asyncio
import json
import os
import sys

from switchboard.simulator.drive import drive_call


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Drive a fake inbound call through Switchboard")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("SWITCHBOARD_PUBLIC_BASE_URL", "http://localhost:8000"),
    )
    parser.add_argument(
        "--secret",
        default=os.environ.get("SWITCHBOARD_MOCK_WEBHOOK_SECRET", "dev-mock-secret"),
    )
    parser.add_argument("--from-number", default="+15551110000")
    parser.add_argument("--to-number", default="+15552220000")
    parser.add_argument("--provider-call-id", default=None)
    args = parser.parse_args(argv)
    result = asyncio.run(
        drive_call(
            base_url=args.base_url,
            secret=args.secret,
            from_number=args.from_number,
            to_number=args.to_number,
            provider_call_id=args.provider_call_id,
        )
    )
    print(json.dumps(result.as_dict(), indent=2))
    raise SystemExit(0 if result.ok else 1)


if __name__ == "__main__":
    main(sys.argv[1:])
