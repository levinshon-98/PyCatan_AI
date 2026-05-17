#!/usr/bin/env python3
"""Hugging Face Spaces entrypoint for the standalone PyCatan replay viewer."""

import os
import sys


def main() -> None:
    port = os.environ.get("PORT", "7860")

    # Spaces needs the HTTP server to listen publicly inside the container.
    # Local scripts keep their safer localhost default.
    os.environ.setdefault("REPLAY_VIEWER_REQUIRE_PUBLIC_CONFIG", "1")
    from examples.ai_testing.replay_viewer import main as replay_main

    sys.argv = [
        "replay_viewer.py",
        "--host",
        "0.0.0.0",
        "--port",
        port,
        "--no-browser",
    ]
    replay_main()


if __name__ == "__main__":
    main()
