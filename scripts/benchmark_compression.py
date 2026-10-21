"""Utilities for measuring error-log compression on a checked-in corpus."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from errdoc.compressor import compress_log

_TOKEN_PROXY = re.compile(r"\w+|[^\w\s]", re.UNICODE)
DEFAULT_CORPUS = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "compression_corpus.json"


def load_corpus(path: str | Path = DEFAULT_CORPUS) -> list[dict[str, Any]]:
    """Load the public, synthetic benchmark logs."""
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def render_log(case: dict[str, Any]) -> str:
    """Expand one fixture into a multiline log without storing huge repeated files."""
    parts = [*case.get("prefix", [])]
    repeated = case.get("repeat_line", "")
    if repeated:
        parts.extend([repeated] * int(case.get("repeat_count", 0)))
    parts.extend(case.get("suffix", []))
    return "\n".join(parts)


def token_proxy(text: str) -> int:
    """Count word/punctuation units as a model-independent approximation."""
    return len(_TOKEN_PROXY.findall(text))


def evaluate_case(case: dict[str, Any]) -> dict[str, Any]:
    raw = render_log(case)
    compressed = compress_log(raw)
    original_units = token_proxy(raw)
    compressed_units = token_proxy(compressed)
    reduction = (original_units - compressed_units) / original_units if original_units else 0.0
    missing = [marker for marker in case.get("required", []) if marker not in compressed]
    leaked = [marker for marker in case.get("forbidden", []) if marker in compressed]
    return {
        "name": case["name"],
        "original_chars": len(raw),
        "compressed_chars": len(compressed),
        "character_reduction": (len(raw) - len(compressed)) / len(raw) if raw else 0.0,
        "original_units": original_units,
        "compressed_units": compressed_units,
        "reduction": reduction,
        "preserved": not missing,
        "missing_markers": missing,
        "secret_leak": bool(leaked),
        "compressed": compressed,
    }


def evaluate_corpus(cases: list[dict[str, Any]]) -> dict[str, Any]:
    results = [evaluate_case(case) for case in cases]
    original = sum(result["original_units"] for result in results)
    compressed = sum(result["compressed_units"] for result in results)
    original_chars = sum(result["original_chars"] for result in results)
    compressed_chars = sum(result["compressed_chars"] for result in results)
    return {
        "results": results,
        "original_chars": original_chars,
        "compressed_chars": compressed_chars,
        "aggregate_character_reduction": (original_chars - compressed_chars) / original_chars if original_chars else 0.0,
        "original_units": original,
        "compressed_units": compressed,
        "aggregate_reduction": (original - compressed) / original if original else 0.0,
        "preserved_all": all(result["preserved"] for result in results),
        "no_secret_leaks": all(not result["secret_leak"] for result in results),
    }


def main() -> int:
    cases = load_corpus()
    report = evaluate_corpus(cases)
    print(f"Corpus cases: {len(cases)}")
    print(
        f"Characters: {report['original_chars']} -> {report['compressed_chars']} "
        f"({report['aggregate_character_reduction']:.1%} reduction)"
    )
    print(
        f"Approximate token units: {report['original_units']} -> "
        f"{report['compressed_units']} "
        f"({report['aggregate_reduction']:.1%} reduction)"
    )
    for result in report["results"]:
        status = "PASS" if result["preserved"] and not result["secret_leak"] else "FAIL"
        print(
            f"{status:4} {result['name']}: {result['original_chars']} chars, "
            f"{result['original_units']} -> "
            f"{result['compressed_units']} ({result['reduction']:.1%})"
        )
        for marker in result["missing_markers"]:
            print(f"     missing required marker: {marker}")
    return 0 if report["preserved_all"] and report["no_secret_leaks"] and report["aggregate_reduction"] >= 0.90 else 1


if __name__ == "__main__":
    raise SystemExit(main())
