#!/usr/bin/env python3
"""Create and optionally push this repo to a Hugging Face Docker Space."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


try:
    import certifi

    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
except Exception:
    pass


def run(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        check=check,
        text=True,
        capture_output=True,
    )


def remote_exists(name: str) -> bool:
    result = run(["git", "remote"], check=True)
    return name in result.stdout.splitlines()


def configure_insecure_hf_http() -> None:
    import httpx
    from huggingface_hub.utils import set_client_factory

    def factory() -> httpx.Client:
        return httpx.Client(follow_redirects=True, timeout=None, verify=False)

    set_client_factory(factory)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare/push a Hugging Face Docker Space.")
    parser.add_argument("repo_id", help="Space repo id, for example: shon98/PyCatan-AI")
    parser.add_argument("--push", action="store_true", help="Push HEAD to the Space main branch.")
    parser.add_argument("--remote", default="hf", help="Git remote name to create/update.")
    args = parser.parse_args()

    try:
        from huggingface_hub import HfApi
    except ImportError:
        print("huggingface_hub is not installed. Run: python -m pip install -U huggingface_hub")
        return 1

    print("[1/4] Checking committable files for API-key patterns...")
    secret_check = run([sys.executable, "scripts/check_no_secrets.py"], check=False)
    print(secret_check.stdout, end="")
    if secret_check.returncode != 0:
        print(secret_check.stderr, end="")
        return secret_check.returncode

    print("[2/4] Checking Hugging Face login...")
    api = HfApi()
    try:
        whoami = api.whoami()
    except Exception as exc:
        if "CERTIFICATE_VERIFY_FAILED" not in str(exc):
            print(f"Could not verify Hugging Face login: {exc}")
            print("Run: hf auth login")
            return 1
        print("SSL verification failed with the local certificate store; retrying with verification disabled for this deploy process.")
        configure_insecure_hf_http()
        api = HfApi()
        try:
            whoami = api.whoami()
        except Exception as retry_exc:
            print(f"Could not verify Hugging Face login: {retry_exc}")
            print("Run: hf auth login")
            return 1
    print(f"Logged in as: {whoami.get('name') or whoami.get('fullname') or 'unknown'}")

    print("[3/4] Creating/updating Docker Space repo...")
    api.create_repo(
        repo_id=args.repo_id,
        repo_type="space",
        space_sdk="docker",
        exist_ok=True,
    )

    remote_url = f"https://huggingface.co/spaces/{args.repo_id}"
    if remote_exists(args.remote):
        run(["git", "remote", "set-url", args.remote, remote_url])
    else:
        run(["git", "remote", "add", args.remote, remote_url])
    print(f"Remote '{args.remote}' -> {remote_url}")

    print("[4/4] Ready.")
    if args.push:
        print("Pushing HEAD to Space main...")
        push = subprocess.run(["git", "push", args.remote, "HEAD:main"], cwd=ROOT)
        return push.returncode

    print(f"To deploy, run: git push {args.remote} HEAD:main")
    return 0


if __name__ == "__main__":
    sys.exit(main())
