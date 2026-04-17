#!/usr/bin/env python3
"""
Convert Mermaid diagram code to SVG using mermaid-cli (mmdc).

Requires:
    npm install -g @mermaid-js/mermaid-cli

Usage:
    python3 mermaid_to_svg.py --input diagram.mmd --output diagram.svg
    python3 mermaid_to_svg.py --code "graph TD; A-->B;" --output diagram.svg
"""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path


def check_mmdc() -> bool:
    """Check if mermaid-cli (mmdc) is installed."""
    try:
        subprocess.run(
            ["mmdc", "--version"],
            capture_output=True,
            timeout=10,
        )
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def mermaid_to_svg(code: str, output_path: str) -> bool:
    """Convert Mermaid code to SVG."""
    if not check_mmdc():
        print("Error: mermaid-cli (mmdc) is not installed.", file=sys.stderr)
        print("Install it with: npm install -g @mermaid-js/mermaid-cli", file=sys.stderr)
        return False

    with tempfile.NamedTemporaryFile(mode="w", suffix=".mmd", delete=False) as f:
        f.write(code)
        input_path = f.name

    try:
        result = subprocess.run(
            ["mmdc", "-i", input_path, "-o", output_path, "-b", "transparent"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            print(f"SVG generated: {Path(output_path).absolute()}")
            return True
        else:
            print(f"mmdc error: {result.stderr}", file=sys.stderr)
            return False
    except subprocess.TimeoutExpired:
        print("Error: mmdc timed out", file=sys.stderr)
        return False
    finally:
        Path(input_path).unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description="Convert Mermaid to SVG")
    parser.add_argument("--input", help="Path to .mmd file")
    parser.add_argument("--code", help="Mermaid code string")
    parser.add_argument("--output", required=True, help="Output SVG path")
    args = parser.parse_args()

    if args.input:
        code = Path(args.input).read_text(encoding="utf-8")
    elif args.code:
        code = args.code
    else:
        print("Error: Provide either --input or --code", file=sys.stderr)
        sys.exit(1)

    if not mermaid_to_svg(code, args.output):
        # Output the raw Mermaid code so the user can render it manually
        print("\nMermaid code (render manually at https://mermaid.live):")
        print(code)
        sys.exit(1)


if __name__ == "__main__":
    main()
