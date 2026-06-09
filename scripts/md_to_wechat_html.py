#!/usr/bin/env python3
"""
Convert Markdown to WeChat-compatible styled HTML.

All styles are inline (WeChat strips <style> blocks and CSS classes).
Produces clean, elegant Chinese typography suitable for WeChat Official Account articles.

Usage:
    python3 md_to_wechat_html.py input.md [output.html] [--theme NAME]

Available themes: professional (default), sspai, github, minimal
"""

import argparse
import re
import sys
import html
from pathlib import Path


# ── Theme definitions ────────────────────────────────────────────────────

_FONT_STACK = (
    "-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC',"
    "'Hiragino Sans GB','Microsoft YaHei',sans-serif"
)
_CODE_FONT = "Menlo,Monaco,'Courier New',monospace"


def _theme_professional() -> dict:
    """干净专业蓝 — 适合技术分析、产品解读（默认主题）"""
    accent = "#2563eb"
    return {
        "container": (
            f"max-width:100%;padding:20px;background:#fff;"
            f"font-family:{_FONT_STACK};"
            f"font-size:16px;line-height:1.8;color:#333;word-wrap:break-word;"
        ),
        "h1": (
            "font-size:24px;font-weight:bold;color:#1a1a1a;text-align:center;"
            "margin:30px 0 20px 0;line-height:1.4;"
        ),
        "h2": (
            "font-size:20px;font-weight:bold;color:#1a1a1a;"
            f"margin:28px 0 16px 0;padding-left:12px;"
            f"border-left:3px solid {accent};line-height:1.4;"
        ),
        "h3": (
            "font-size:18px;font-weight:bold;color:#333;"
            "margin:24px 0 12px 0;line-height:1.4;"
        ),
        "h4": (
            "font-size:16px;font-weight:bold;color:#555;"
            "margin:20px 0 10px 0;line-height:1.4;"
        ),
        "p": "margin:0 0 16px 0;line-height:1.8;color:#333;",
        "blockquote": (
            f"margin:16px 0;padding:15px 20px;background:#eff6ff;"
            f"border-left:3px solid {accent};color:#555;font-style:italic;"
            f"line-height:1.8;"
        ),
        "blockquote_p": "margin:0 0 8px 0;line-height:1.8;color:#555;",
        "code_block": (
            f"margin:16px 0;padding:16px;background:#1e293b;border-radius:6px;"
            f"font-family:{_CODE_FONT};font-size:14px;"
            f"line-height:1.6;overflow-x:auto;white-space:pre-wrap;word-wrap:break-word;"
            f"color:#e2e8f0;"
        ),
        "inline_code": (
            f"background:#eff6ff;padding:2px 6px;border-radius:3px;"
            f"font-family:{_CODE_FONT};"
            f"font-size:14px;color:{accent};"
        ),
        "ul": "margin:0 0 16px 0;padding-left:24px;",
        "ol": "margin:0 0 16px 0;padding-left:24px;",
        "li": "margin:0 0 8px 0;line-height:1.8;color:#333;",
        "hr": "border:none;border-top:1px solid #e2e8f0;margin:30px 0;",
        "img": "max-width:100%;display:block;margin:16px auto;border-radius:6px;",
        "a": f"color:{accent};text-decoration:none;",
        "strong": "font-weight:bold;color:#1a1a1a;",
        "em": "font-style:italic;",
        "table": (
            "width:100%;border-collapse:collapse;margin:16px 0;"
            "font-size:14px;line-height:1.6;"
        ),
        "th": (
            f"border:1px solid #dbeafe;padding:10px 12px;background:#eff6ff;"
            f"font-weight:bold;text-align:left;color:#1e40af;"
        ),
        "td": "border:1px solid #dbeafe;padding:10px 12px;color:#333;",
        "footnote": "font-size:14px;color:#999;margin-top:40px;padding-top:20px;border-top:1px solid #e2e8f0;",
    }


def _theme_sspai() -> dict:
    """少数派风暖白红 — 适合数字生活、工具评测"""
    accent = "#c7372f"
    return {
        "container": (
            f"max-width:100%;padding:20px;background:#fafaf7;"
            f"font-family:{_FONT_STACK};"
            f"font-size:16px;line-height:1.8;color:#333;word-wrap:break-word;"
        ),
        "h1": (
            "font-size:24px;font-weight:bold;color:#1a1a1a;text-align:center;"
            "margin:30px 0 20px 0;line-height:1.4;"
        ),
        "h2": (
            "font-size:20px;font-weight:bold;color:#1a1a1a;"
            "margin:28px 0 16px 0;padding-bottom:8px;"
            f"border-bottom:2px solid {accent};line-height:1.4;"
        ),
        "h3": (
            "font-size:18px;font-weight:bold;color:#333;"
            f"margin:24px 0 12px 0;padding-left:12px;"
            f"border-left:3px solid {accent};line-height:1.4;"
        ),
        "h4": (
            "font-size:16px;font-weight:bold;color:#555;"
            "margin:20px 0 10px 0;line-height:1.4;"
        ),
        "p": "margin:0 0 16px 0;line-height:1.8;color:#333;",
        "blockquote": (
            f"margin:16px 0;padding:15px 20px;background:#f5f2ed;"
            f"border-left:3px solid {accent};color:#666;font-style:italic;"
            f"line-height:1.8;"
        ),
        "blockquote_p": "margin:0 0 8px 0;line-height:1.8;color:#666;",
        "code_block": (
            f"margin:16px 0;padding:16px;background:#f5f2ed;border-radius:6px;"
            f"font-family:{_CODE_FONT};font-size:14px;"
            f"line-height:1.6;overflow-x:auto;white-space:pre-wrap;word-wrap:break-word;"
            f"color:#333;"
        ),
        "inline_code": (
            f"background:#f5f2ed;padding:2px 6px;border-radius:3px;"
            f"font-family:{_CODE_FONT};"
            f"font-size:14px;color:{accent};"
        ),
        "ul": "margin:0 0 16px 0;padding-left:24px;",
        "ol": "margin:0 0 16px 0;padding-left:24px;",
        "li": "margin:0 0 8px 0;line-height:1.8;color:#333;",
        "hr": "border:none;border-top:1px solid #e0ddd7;margin:30px 0;",
        "img": "max-width:100%;display:block;margin:16px auto;border-radius:6px;",
        "a": f"color:{accent};text-decoration:none;",
        "strong": "font-weight:bold;color:#1a1a1a;",
        "em": "font-style:italic;",
        "table": (
            "width:100%;border-collapse:collapse;margin:16px 0;"
            "font-size:14px;line-height:1.6;"
        ),
        "th": (
            f"border:1px solid #e0ddd7;padding:10px 12px;background:#f5f2ed;"
            f"font-weight:bold;text-align:left;color:#333;"
        ),
        "td": "border:1px solid #e0ddd7;padding:10px 12px;color:#333;",
        "footnote": "font-size:14px;color:#999;margin-top:40px;padding-top:20px;border-top:1px solid #e0ddd7;",
    }


def _theme_github() -> dict:
    """GitHub 白底蓝 — 适合代码多的技术教程"""
    accent = "#0969da"
    return {
        "container": (
            f"max-width:100%;padding:20px;background:#fff;"
            f"font-family:{_FONT_STACK};"
            f"font-size:16px;line-height:1.8;color:#1f2328;word-wrap:break-word;"
        ),
        "h1": (
            "font-size:24px;font-weight:bold;color:#1f2328;"
            "margin:30px 0 16px 0;padding-bottom:8px;"
            "border-bottom:1px solid #d1d9e0;line-height:1.4;"
        ),
        "h2": (
            "font-size:20px;font-weight:bold;color:#1f2328;"
            "margin:28px 0 16px 0;padding-bottom:6px;"
            "border-bottom:1px solid #d1d9e0;line-height:1.4;"
        ),
        "h3": (
            "font-size:18px;font-weight:bold;color:#1f2328;"
            "margin:24px 0 12px 0;line-height:1.4;"
        ),
        "h4": (
            "font-size:16px;font-weight:bold;color:#1f2328;"
            "margin:20px 0 10px 0;line-height:1.4;"
        ),
        "p": "margin:0 0 16px 0;line-height:1.8;color:#1f2328;",
        "blockquote": (
            "margin:16px 0;padding:12px 20px;background:transparent;"
            "border-left:3px solid #d1d9e0;color:#656d76;font-style:normal;"
            "line-height:1.8;"
        ),
        "blockquote_p": "margin:0 0 8px 0;line-height:1.8;color:#656d76;",
        "code_block": (
            f"margin:16px 0;padding:16px;background:#f6f8fa;border-radius:6px;"
            f"border:1px solid #d1d9e0;"
            f"font-family:{_CODE_FONT};font-size:14px;"
            f"line-height:1.6;overflow-x:auto;white-space:pre-wrap;word-wrap:break-word;"
            f"color:#1f2328;"
        ),
        "inline_code": (
            f"background:#eff1f3;padding:2px 6px;border-radius:3px;"
            f"font-family:{_CODE_FONT};"
            f"font-size:14px;color:#1f2328;"
        ),
        "ul": "margin:0 0 16px 0;padding-left:24px;",
        "ol": "margin:0 0 16px 0;padding-left:24px;",
        "li": "margin:0 0 4px 0;line-height:1.8;color:#1f2328;",
        "hr": "border:none;border-top:2px solid #d1d9e0;margin:30px 0;",
        "img": "max-width:100%;display:block;margin:16px auto;border-radius:6px;",
        "a": f"color:{accent};text-decoration:none;",
        "strong": "font-weight:bold;color:#1f2328;",
        "em": "font-style:italic;",
        "table": (
            "width:100%;border-collapse:collapse;margin:16px 0;"
            "font-size:14px;line-height:1.6;"
        ),
        "th": (
            "border:1px solid #d1d9e0;padding:8px 12px;background:#f6f8fa;"
            "font-weight:bold;text-align:left;color:#1f2328;"
        ),
        "td": "border:1px solid #d1d9e0;padding:8px 12px;color:#1f2328;",
        "footnote": "font-size:14px;color:#656d76;margin-top:40px;padding-top:20px;border-top:1px solid #d1d9e0;",
    }


def _theme_minimal() -> dict:
    """极简黑白灰 — 适合深度分析、长篇论述"""
    return {
        "container": (
            f"max-width:100%;padding:20px;background:#fff;"
            f"font-family:{_FONT_STACK};"
            f"font-size:16px;line-height:2;color:#333;word-wrap:break-word;"
        ),
        "h1": (
            "font-size:24px;font-weight:bold;color:#111;text-align:center;"
            "margin:36px 0 24px 0;line-height:1.4;"
        ),
        "h2": (
            "font-size:20px;font-weight:bold;color:#111;"
            "margin:32px 0 16px 0;line-height:1.4;"
        ),
        "h3": (
            "font-size:18px;font-weight:bold;color:#222;"
            "margin:24px 0 12px 0;line-height:1.4;"
        ),
        "h4": (
            "font-size:16px;font-weight:bold;color:#444;"
            "margin:20px 0 10px 0;line-height:1.4;"
        ),
        "p": "margin:0 0 16px 0;line-height:2;color:#333;",
        "blockquote": (
            "margin:16px 0;padding:15px 20px;background:#f9f9f9;"
            "border-left:3px solid #999;color:#666;font-style:italic;"
            "line-height:1.8;"
        ),
        "blockquote_p": "margin:0 0 8px 0;line-height:1.8;color:#666;",
        "code_block": (
            f"margin:16px 0;padding:16px;background:#f5f5f5;border-radius:4px;"
            f"font-family:{_CODE_FONT};font-size:14px;"
            f"line-height:1.6;overflow-x:auto;white-space:pre-wrap;word-wrap:break-word;"
            f"color:#333;"
        ),
        "inline_code": (
            f"background:#f0f0f0;padding:2px 6px;border-radius:3px;"
            f"font-family:{_CODE_FONT};"
            f"font-size:14px;color:#333;"
        ),
        "ul": "margin:0 0 16px 0;padding-left:24px;",
        "ol": "margin:0 0 16px 0;padding-left:24px;",
        "li": "margin:0 0 8px 0;line-height:1.8;color:#333;",
        "hr": "border:none;border-top:1px solid #ddd;margin:30px 0;",
        "img": "max-width:100%;display:block;margin:16px auto;",
        "a": "color:#333;text-decoration:underline;",
        "strong": "font-weight:bold;color:#111;",
        "em": "font-style:italic;",
        "table": (
            "width:100%;border-collapse:collapse;margin:16px 0;"
            "font-size:14px;line-height:1.6;"
        ),
        "th": (
            "border:1px solid #ddd;padding:10px 12px;background:#f5f5f5;"
            "font-weight:bold;text-align:left;color:#333;"
        ),
        "td": "border:1px solid #ddd;padding:10px 12px;color:#333;",
        "footnote": "font-size:14px;color:#999;margin-top:40px;padding-top:20px;border-top:1px solid #ddd;",
    }


def _theme_garden() -> dict:
    """温暖园丁风 — 适合教育、亲子、散文"""
    accent = "#b5651d"
    return {
        "container": (
            f"max-width:100%;padding:20px;background:#fdf8f0;"
            f"font-family:{_FONT_STACK};"
            f"font-size:16px;line-height:2.0;color:#3d2b1f;word-wrap:break-word;"
        ),
        "h1": (
            "font-size:24px;font-weight:bold;color:#3d2b1f;text-align:center;"
            "margin:30px 0 10px 0;line-height:1.4;"
        ),
        "h2": (
            "font-size:20px;font-weight:bold;color:#3d2b1f;"
            f"margin:28px 0 16px 0;padding-left:12px;"
            f"border-left:3px solid {accent};line-height:1.4;"
        ),
        "h3": (
            "font-size:18px;font-weight:bold;color:#4a3728;"
            "margin:24px 0 12px 0;line-height:1.4;"
        ),
        "h4": (
            "font-size:16px;font-weight:bold;color:#5a4a3a;"
            "margin:20px 0 10px 0;line-height:1.4;"
        ),
        "p": "margin:0 0 18px 0;line-height:2.0;color:#3d2b1f;",
        "blockquote": (
            f"margin:16px 0;padding:15px 20px;background:#f7f0e7;"
            f"border-left:3px solid {accent};color:#5a4a3a;font-style:normal;"
            f"line-height:1.8;border-radius:0 6px 6px 0;"
        ),
        "blockquote_p": "margin:0 0 8px 0;line-height:1.8;color:#5a4a3a;",
        "code_block": (
            f"margin:16px 0;padding:16px;background:#f7f0e7;border-radius:6px;"
            f"font-family:{_CODE_FONT};font-size:14px;"
            f"line-height:1.6;overflow-x:auto;white-space:pre-wrap;word-wrap:break-word;"
            f"color:#3d2b1f;"
        ),
        "inline_code": (
            f"background:#f7f0e7;padding:2px 6px;border-radius:3px;"
            f"font-family:{_CODE_FONT};"
            f"font-size:14px;color:{accent};"
        ),
        "ul": "margin:0 0 16px 0;padding-left:24px;",
        "ol": "margin:0 0 16px 0;padding-left:24px;",
        "li": "margin:0 0 8px 0;line-height:2.0;color:#3d2b1f;",
        "hr": f"border:none;border-top:1px solid #e0d5c7;margin:30px 0;",
        "img": "max-width:100%;display:block;margin:20px auto;border-radius:8px;",
        "a": f"color:{accent};text-decoration:none;",
        "strong": "font-weight:bold;color:#3d2b1f;",
        "em": "font-style:italic;color:#5a4a3a;",
        "table": (
            "width:100%;border-collapse:collapse;margin:16px 0;"
            "font-size:14px;line-height:1.6;"
        ),
        "th": (
            f"border:1px solid #e0d5c7;padding:10px 12px;background:#f7f0e7;"
            f"font-weight:bold;text-align:left;color:#3d2b1f;"
        ),
        "td": "border:1px solid #e0d5c7;padding:10px 12px;color:#3d2b1f;",
        "footnote": "font-size:14px;color:#8a7a6a;margin-top:40px;padding-top:20px;border-top:1px solid #e0d5c7;",
    }


_THEMES = {
    "professional": _theme_professional,
    "sspai": _theme_sspai,
    "github": _theme_github,
    "minimal": _theme_minimal,
    "garden": _theme_garden,
}

AVAILABLE_THEMES = list(_THEMES.keys())


def get_theme(name: str) -> dict:
    """Return the STYLES dict for the given theme name."""
    factory = _THEMES.get(name)
    if factory is None:
        print(f"Error: Unknown theme '{name}'. Available: {', '.join(AVAILABLE_THEMES)}")
        sys.exit(1)
    return factory()


# ── Markdown parsing helpers ──────────────────────────────────────────────

def escape(text: str) -> str:
    """Escape HTML entities but preserve already-converted HTML."""
    return html.escape(text, quote=False)


def process_inline(text: str, styles: dict) -> str:
    """Process inline Markdown elements: bold, italic, code, links, images."""
    # Images first: ![alt](url)
    text = re.sub(
        r'!\[([^\]]*)\]\(([^)]+)\)',
        lambda m: f'<img src="{m.group(2)}" alt="{escape(m.group(1))}" style="{styles["img"]}"/>',
        text,
    )
    # Links: [text](url)
    text = re.sub(
        r'\[([^\]]+)\]\(([^)]+)\)',
        lambda m: f'<a href="{m.group(2)}" style="{styles["a"]}">{m.group(1)}</a>',
        text,
    )
    # Bold + italic: ***text*** or ___text___
    text = re.sub(
        r'\*\*\*(.+?)\*\*\*|___(.+?)___',
        lambda m: f'<strong style="{styles["strong"]}"><em style="{styles["em"]}">{m.group(1) or m.group(2)}</em></strong>',
        text,
    )
    # Bold: **text** or __text__
    text = re.sub(
        r'\*\*(.+?)\*\*|__(.+?)__',
        lambda m: f'<strong style="{styles["strong"]}">{m.group(1) or m.group(2)}</strong>',
        text,
    )
    # Italic: *text* or _text_
    text = re.sub(
        r'\*(.+?)\*|_(.+?)_',
        lambda m: f'<em style="{styles["em"]}">{m.group(1) or m.group(2)}</em>',
        text,
    )
    # Inline code: `code`
    text = re.sub(
        r'`([^`]+)`',
        lambda m: f'<code style="{styles["inline_code"]}">{escape(m.group(1))}</code>',
        text,
    )
    return text


def convert_markdown_to_html(md_text: str, theme: str = "professional") -> str:
    """Convert Markdown text to WeChat-compatible HTML with inline styles."""
    styles = get_theme(theme)
    lines = md_text.split("\n")
    html_parts = []
    i = 0
    in_list = None  # 'ul' or 'ol' or None
    in_code_block = False
    code_block_content = []
    in_blockquote = False
    blockquote_content = []
    in_table = False
    table_rows = []
    table_has_header = False

    def flush_list():
        nonlocal in_list
        if in_list:
            html_parts.append(f"</{in_list}>")
            in_list = None

    def flush_blockquote():
        nonlocal in_blockquote, blockquote_content
        if in_blockquote:
            inner = "".join(
                f'<p style="{styles["blockquote_p"]}">{process_inline(line, styles)}</p>'
                for line in blockquote_content
                if line.strip()
            )
            html_parts.append(f'<blockquote style="{styles["blockquote"]}">{inner}</blockquote>')
            blockquote_content = []
            in_blockquote = False

    def flush_table():
        nonlocal in_table, table_rows, table_has_header
        if in_table and table_rows:
            table_html = f'<table style="{styles["table"]}">'
            for idx, row in enumerate(table_rows):
                cells = [c.strip() for c in row.strip("|").split("|")]
                tag = "th" if idx == 0 else "td"
                style = styles[tag]
                row_html = "".join(f'<{tag} style="{style}">{process_inline(c, styles)}</{tag}>' for c in cells)
                table_html += f"<tr>{row_html}</tr>"
            table_html += "</table>"
            html_parts.append(table_html)
            table_rows = []
            table_has_header = False
            in_table = False

    while i < len(lines):
        line = lines[i]

        # Code blocks (``` ... ```)
        if line.strip().startswith("```"):
            if in_code_block:
                code_text = escape("\n".join(code_block_content))
                html_parts.append(f'<pre style="{styles["code_block"]}"><code>{code_text}</code></pre>')
                code_block_content = []
                in_code_block = False
            else:
                flush_list()
                flush_blockquote()
                flush_table()
                in_code_block = True
            i += 1
            continue

        if in_code_block:
            code_block_content.append(line)
            i += 1
            continue

        # Table rows
        if "|" in line and line.strip().startswith("|"):
            # Check if this is the separator row (e.g., |---|---|)
            if re.match(r'^\s*\|[\s\-:|]+\|\s*$', line):
                table_has_header = True
                i += 1
                continue
            if not in_table:
                flush_list()
                flush_blockquote()
                in_table = True
            table_rows.append(line)
            i += 1
            continue
        else:
            flush_table()

        # Blockquotes
        if line.strip().startswith(">"):
            flush_list()
            in_blockquote = True
            content = re.sub(r"^>\s?", "", line.strip())
            blockquote_content.append(content)
            i += 1
            continue
        else:
            flush_blockquote()

        # Headings
        heading_match = re.match(r'^(#{1,4})\s+(.+)$', line.strip())
        if heading_match:
            flush_list()
            level = len(heading_match.group(1))
            text = process_inline(heading_match.group(2), styles)
            tag = f"h{level}"
            style = styles.get(tag, styles["h4"])
            html_parts.append(f'<{tag} style="{style}">{text}</{tag}>')
            i += 1
            continue

        # Horizontal rules
        if re.match(r'^\s*([-*_])\s*\1\s*\1[\s\-*_]*$', line.strip()) and len(line.strip()) >= 3:
            flush_list()
            html_parts.append(f'<hr style="{styles["hr"]}"/>')
            i += 1
            continue

        # Unordered list items
        ul_match = re.match(r'^(\s*)[-*+]\s+(.+)$', line)
        if ul_match:
            if in_list != "ul":
                flush_list()
                in_list = "ul"
                html_parts.append(f'<ul style="{styles["ul"]}">')
            text = process_inline(ul_match.group(2), styles)
            html_parts.append(f'<li style="{styles["li"]}">{text}</li>')
            i += 1
            continue

        # Ordered list items
        ol_match = re.match(r'^(\s*)\d+\.\s+(.+)$', line)
        if ol_match:
            if in_list != "ol":
                flush_list()
                in_list = "ol"
                html_parts.append(f'<ol style="{styles["ol"]}">')
            text = process_inline(ol_match.group(2), styles)
            html_parts.append(f'<li style="{styles["li"]}">{text}</li>')
            i += 1
            continue

        # Empty line
        if not line.strip():
            flush_list()
            i += 1
            continue

        # Regular paragraph
        flush_list()
        text = process_inline(line.strip(), styles)
        html_parts.append(f'<p style="{styles["p"]}">{text}</p>')
        i += 1

    # Flush remaining state
    flush_list()
    flush_blockquote()
    flush_table()
    if in_code_block and code_block_content:
        code_text = escape("\n".join(code_block_content))
        html_parts.append(f'<pre style="{styles["code_block"]}"><code>{code_text}</code></pre>')

    body = "\n".join(html_parts)
    return f'<section style="{styles["container"]}">\n{body}\n</section>'


def main():
    parser = argparse.ArgumentParser(
        description="Convert Markdown to WeChat-compatible styled HTML."
    )
    parser.add_argument("input", help="Path to input Markdown file")
    parser.add_argument("output", nargs="?", help="Path to output HTML file (default: same name with .html)")
    parser.add_argument(
        "--theme", choices=AVAILABLE_THEMES, default="professional",
        help=f"Visual theme (default: professional). Options: {', '.join(AVAILABLE_THEMES)}"
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: File not found: {input_path}")
        sys.exit(1)

    md_text = input_path.read_text(encoding="utf-8")
    html_output = convert_markdown_to_html(md_text, theme=args.theme)

    # Wrap in a minimal HTML document for preview
    full_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{input_path.stem}</title>
<style>
  body {{ margin: 0; padding: 20px; background: #f5f5f5; }}
  .wechat-preview {{
    max-width: 580px; margin: 0 auto; background: #fff;
    box-shadow: 0 2px 12px rgba(0,0,0,0.1); border-radius: 8px;
    overflow: hidden;
  }}
</style>
</head>
<body>
<div class="wechat-preview">
{html_output}
</div>
</body>
</html>"""

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = input_path.with_suffix(".html")

    output_path.write_text(full_html, encoding="utf-8")
    print(f"[{args.theme}] WeChat HTML generated: {output_path.absolute()}")

    # Also save just the inner HTML (for pasting into WeChat editor)
    inner_path = input_path.with_name(input_path.stem + "_wechat_inner.html")
    inner_path.write_text(html_output, encoding="utf-8")
    print(f"Inner HTML (for WeChat editor): {inner_path.absolute()}")


if __name__ == "__main__":
    main()
