#!/usr/bin/env python3
"""
Generate images for WeChat articles using Google Gemini API (Imagen).

Requires:
    - GOOGLE_AI_API_KEY environment variable
    - google-genai package: pip install google-genai

Usage:
    python3 generate_image.py --prompt "描述" --output cover.png
    python3 generate_image.py --prompt "描述" --output cover.png --style illustration
"""

import argparse
import base64
import json
import os
import sys
from pathlib import Path

try:
    from google import genai
    from google.genai import types
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False


# Fallback: use requests directly if google-genai is not installed
def generate_with_requests(prompt: str, output_path: str, api_key: str) -> bool:
    """Generate image using Gemini API via direct HTTP request."""
    import urllib.request
    import urllib.error

    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-image:generateContent"

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        candidates = result.get("candidates", [])
        for candidate in candidates:
            parts = candidate.get("content", {}).get("parts", [])
            for part in parts:
                if "inlineData" in part:
                    img_data = base64.b64decode(part["inlineData"]["data"])
                    Path(output_path).write_bytes(img_data)
                    return True

        print("Error: No image data in API response", file=sys.stderr)
        return False

    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"API error {e.code}: {body}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return False


def generate_with_genai(prompt: str, output_path: str, api_key: str) -> bool:
    """Generate image using the google-genai SDK (Imagen 4.0)."""
    client = genai.Client(api_key=api_key)

    try:
        # Primary: use Imagen 4.0 for dedicated image generation
        response = client.models.generate_images(
            model="imagen-4.0-ultra-generate-001",
            prompt=prompt,
            config=types.GenerateImagesConfig(number_of_images=1),
        )
        if response.generated_images:
            img_data = response.generated_images[0].image.image_bytes
            Path(output_path).write_bytes(img_data)
            return True

        print("Error: No image data in API response", file=sys.stderr)
        return False

    except Exception as e:
        # Fallback: try gemini-2.5-flash-image for multimodal generation
        print(f"Imagen failed ({e}), trying gemini-2.5-flash-image...", file=sys.stderr)
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash-image",
                contents=prompt,
                config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"]),
            )
            for part in response.candidates[0].content.parts:
                if part.inline_data is not None:
                    img_data = part.inline_data.data
                    if isinstance(img_data, str):
                        img_data = base64.b64decode(img_data)
                    Path(output_path).write_bytes(img_data)
                    return True
        except Exception as e2:
            print(f"Fallback also failed: {e2}", file=sys.stderr)
        return False


STYLE_PROMPTS = {
    "cover": "Create a modern, clean cover image for a WeChat article. Style: minimalist, professional, with subtle gradients. ",
    "illustration": "Create a flat-style illustration suitable for a Chinese tech blog article. Clean lines, modern colors. ",
    "diagram": "Create a clear, professional diagram or infographic. Use clean lines and readable text. ",
    "photo": "Create a photorealistic image. High quality, well-lit, professional composition. ",
}


def main():
    parser = argparse.ArgumentParser(description="Generate images via Gemini API")
    parser.add_argument("--prompt", required=True, help="Image description")
    parser.add_argument("--output", required=True, help="Output file path")
    parser.add_argument(
        "--style",
        choices=list(STYLE_PROMPTS.keys()),
        default="cover",
        help="Image style preset (default: cover)",
    )
    args = parser.parse_args()

    api_key = os.environ.get("GOOGLE_AI_API_KEY")
    if not api_key:
        print("Error: GOOGLE_AI_API_KEY environment variable is not set", file=sys.stderr)
        print("Set it with: export GOOGLE_AI_API_KEY='your-api-key'", file=sys.stderr)
        sys.exit(1)

    full_prompt = STYLE_PROMPTS.get(args.style, "") + args.prompt

    print(f"Generating image with style '{args.style}'...")
    print(f"Prompt: {full_prompt[:100]}...")

    if HAS_GENAI:
        success = generate_with_genai(full_prompt, args.output, api_key)
    else:
        print("Note: google-genai not installed, using direct HTTP API", file=sys.stderr)
        success = generate_with_requests(full_prompt, args.output, api_key)

    if success:
        size = Path(args.output).stat().st_size
        print(f"Image saved: {Path(args.output).absolute()} ({size:,} bytes)")
    else:
        print("Failed to generate image", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
