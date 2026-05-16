#!/usr/bin/env python3
"""Hugging Face Spaces entrypoint for the public PyCatan demo."""

import os
import sys


def main() -> None:
    port = os.environ.get("PORT", "7860")

    # Spaces needs the HTTP server to listen publicly inside the container.
    # Local scripts keep their safer localhost default.
    os.environ.setdefault("PYCATAN_BIND_HOST", "0.0.0.0")
    os.environ.setdefault("PYCATAN_PUBLIC_HOST", os.environ.get("SPACE_HOST", "localhost"))
    os.environ.setdefault("PYCATAN_NO_BROWSER", "1")

    from examples.ai_testing.play_with_openrouter import main as openrouter_main

    sys.argv = ["play_with_openrouter.py", "--port", port]
    openrouter_main()


if __name__ == "__main__":
    main()
