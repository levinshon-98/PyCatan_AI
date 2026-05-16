#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compare OpenRouter models on one saved PyCatan prompt."""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from examples.ai_testing.play_with_ai import load_env_file
from pycatan.ai.llm_client import OpenRouterClient
from pycatan.ai.response_parser import ResponseParser
from pycatan.ai.schemas import ResponseType


DEFAULT_MODELS = [
    "openai/gpt-4o-mini",
    "anthropic/claude-sonnet-4.5",
    "google/gemini-2.5-flash",
]

DEFAULT_PROMPT = (
    Path("examples")
    / "ai_testing"
    / "my_games"
    / "session_20260516_032115"
    / "Ziv"
    / "prompts"
    / "prompt_1.json"
)


def load_prompt_doc(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        doc = json.load(handle)

    if not isinstance(doc.get("prompt"), dict):
        raise ValueError(f"{path} does not look like a saved PyCatan prompt JSON")
    if not isinstance(doc.get("response_schema"), dict):
        raise ValueError(f"{path} is missing response_schema")
    if not isinstance(doc.get("tools_schema"), list):
        raise ValueError(f"{path} is missing tools_schema")

    doc["_path"] = str(path)
    return doc


def load_models(args: argparse.Namespace) -> List[str]:
    models: List[str] = []
    if args.models:
        models.extend(args.models)
    if args.models_file:
        for line in Path(args.models_file).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                models.append(line)
    return models or list(DEFAULT_MODELS)


def allowed_action_types(prompt_doc: Dict[str, Any]) -> List[str]:
    action_types = []
    for action in prompt_doc.get("allowed_actions") or []:
        if isinstance(action, dict) and action.get("type"):
            action_types.append(action["type"])
        elif isinstance(action, str):
            action_types.append(action)
    return action_types


def result_path(output_dir: Path, model: str, suffix: str) -> Path:
    safe_model = model.replace("/", "__").replace(":", "_")
    return output_dir / f"{safe_model}.{suffix}"


def normalize_action_parameters(data: Dict[str, Any]) -> Dict[str, Any]:
    copied = json.loads(json.dumps(data, ensure_ascii=False))
    action = copied.get("action")
    if isinstance(action, dict):
        params = action.get("parameters")
        if isinstance(params, str):
            try:
                parsed = json.loads(params) if params.strip() else {}
            except json.JSONDecodeError:
                parsed = {}
            action["parameters"] = parsed if isinstance(parsed, dict) else {}
    return copied


def probe_model(
    model: str,
    prompt_doc: Dict[str, Any],
    api_key: str,
    output_dir: Path,
    temperature: float,
    max_tokens: int,
    strict_routing: bool,
    dry_run: bool,
) -> Dict[str, Any]:
    prompt_text = json.dumps(prompt_doc["prompt"], indent=2, ensure_ascii=False)
    schema = prompt_doc["response_schema"]
    tools = prompt_doc["tools_schema"]
    parser = ResponseParser(enable_fallbacks=True, strict_mode=False)
    allowed_actions = allowed_action_types(prompt_doc)

    result: Dict[str, Any] = {
        "model": model,
        "prompt_path": prompt_doc["_path"],
        "prompt_chars": len(prompt_text),
        "tools_count": len(tools),
        "strict_routing": strict_routing,
        "request_ok": False,
        "tool_support_ok": None,
        "schema_support_ok": None,
        "json_parse_ok": False,
        "action_valid": False,
        "tool_calls_count": 0,
        "latency_seconds": 0.0,
        "tokens": {},
        "finish_reason": None,
        "error": None,
    }

    if dry_run:
        result.update({
            "request_ok": True,
            "tool_support_ok": True,
            "schema_support_ok": True,
            "dry_run": True,
        })
        return result

    try:
        client = OpenRouterClient(
            model=model,
            api_key=api_key,
            temperature=temperature,
            max_tokens=max_tokens,
            require_parameters=strict_routing,
            allow_parameter_fallback=not strict_routing,
        )
        response = client.generate(
            prompt_text,
            response_schema=schema,
            tools=tools,
            max_tokens=max_tokens,
            temperature=temperature,
        )
    except Exception as exc:
        result["error"] = str(exc)
        return result

    result.update({
        "request_ok": bool(response.success),
        "tool_calls_count": len(response.tool_calls or []),
        "latency_seconds": response.latency_seconds,
        "finish_reason": response.finish_reason,
        "tokens": {
            "prompt": response.prompt_tokens,
            "completion": response.completion_tokens,
            "total": response.total_tokens,
        },
        "error": response.error,
    })

    raw_path = result_path(output_dir, model, "raw.json")
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(
        json.dumps({
            "model": model,
            "success": response.success,
            "content": response.content,
            "tool_calls": response.tool_calls,
            "raw_response": response.raw_response,
            "error": response.error,
        }, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    result["raw_path"] = str(raw_path)

    if not response.success:
        error_text = response.error or ""
        result["tool_support_ok"] = "tool" not in error_text.lower()
        result["schema_support_ok"] = "response_format" not in error_text and "schema" not in error_text.lower()
        return result

    result["tool_support_ok"] = True
    result["schema_support_ok"] = True
    if response.tool_calls:
        result["tool_call_names"] = [call.get("name") for call in response.tool_calls]

    if response.content:
        parsed = parser.parse(response.content, ResponseType.ACTIVE_TURN, allowed_actions=allowed_actions)
        result["json_parse_ok"] = bool(parsed.success)
        if parsed.success and parsed.data:
            normalized = normalize_action_parameters(parsed.data)
            action = normalized.get("action") or {}
            result["action_type"] = action.get("type")
            result["action_parameters_type"] = type(action.get("parameters")).__name__
            action_check = parser._validate_action(action, allowed_actions)
            result["action_valid"] = bool(action_check[0])
            result["action_error"] = action_check[1]
        else:
            result["parse_error"] = parsed.error_message

    return result


def write_summary(results: List[Dict[str, Any]], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    lines = [
        "# OpenRouter Model Probe",
        "",
        "| Model | Request | Tools | Schema | JSON | Action | Tool Calls | Latency | Tokens | Error |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for item in results:
        tokens = item.get("tokens") or {}
        error = (item.get("error") or item.get("parse_error") or item.get("action_error") or "")
        error = error[:90].replace("|", "\\|").replace("\n", " ")
        lines.append(
            "| {model} | {request} | {tools} | {schema} | {json_ok} | {action} | {tool_calls} | {latency:.2f}s | {tokens_total} | {error} |".format(
                model=item["model"],
                request="ok" if item.get("request_ok") else "fail",
                tools="ok" if item.get("tool_support_ok") else "fail",
                schema="ok" if item.get("schema_support_ok") else "fail",
                json_ok="ok" if item.get("json_parse_ok") else "-",
                action="ok" if item.get("action_valid") else "-",
                tool_calls=item.get("tool_calls_count", 0),
                latency=float(item.get("latency_seconds") or 0),
                tokens_total=tokens.get("total", 0),
                error=error,
            )
        )
    (output_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe OpenRouter models using one saved PyCatan prompt")
    parser.add_argument("--prompt", type=Path, default=DEFAULT_PROMPT, help="Saved prompt_N.json to send")
    parser.add_argument("--models", nargs="*", help="OpenRouter model ids to test")
    parser.add_argument("--models-file", help="Text file with one OpenRouter model id per line")
    parser.add_argument("--output-dir", type=Path, default=None, help="Directory for raw outputs and summary")
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--max-tokens", type=int, default=2000)
    parser.add_argument("--strict-routing", action="store_true", help="Require endpoints that support every parameter")
    parser.add_argument("--dry-run", action="store_true", help="Validate setup without API calls")
    args = parser.parse_args()

    load_env_file()
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key and not args.dry_run:
        raise SystemExit("OPENROUTER_API_KEY is missing. Put it in .env or the environment.")

    prompt_doc = load_prompt_doc(args.prompt)
    models = load_models(args)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = args.output_dir or Path("examples") / "ai_testing" / "openrouter_model_tests" / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "prompt_snapshot.json").write_text(
        json.dumps(prompt_doc, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"[PROBE] Prompt: {args.prompt}")
    print(f"[PROBE] Models: {', '.join(models)}")
    print(f"[PROBE] Tools: {len(prompt_doc['tools_schema'])}")
    print(f"[PROBE] Strict routing: {args.strict_routing}")
    print(f"[PROBE] Output: {output_dir}")

    results = []
    for model in models:
        print(f"[PROBE] Testing {model}...")
        result = probe_model(
            model=model,
            prompt_doc=prompt_doc,
            api_key=api_key,
            output_dir=output_dir,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            strict_routing=args.strict_routing,
            dry_run=args.dry_run,
        )
        results.append(result)
        print(f"[PROBE] {model}: {'ok' if result.get('request_ok') else 'fail'}")

    write_summary(results, output_dir)
    print(f"[PROBE] Summary: {output_dir / 'summary.md'}")


if __name__ == "__main__":
    main()
