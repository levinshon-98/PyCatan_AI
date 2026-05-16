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

    from examples.ai_testing.play_public_entry import main as public_main

    sys.argv = ["play_public_entry.py", "--port", port]
    if os.environ.get("OPENROUTER_API_KEY") and os.environ.get("GEMINI_API_KEY"):
        sys.argv.append("--use-env-keys")
    public_main()


if __name__ == "__main__":
    main()
