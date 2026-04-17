---
name: wechat-publisher
description: >
  Format a Markdown article for WeChat publishing. Converts Markdown to styled HTML,
  generates images with AI, and optionally publishes to WeChat drafts. Use when the
  user wants to publish or format an article for WeChat Official Account (公众号).
  Also use when the user says "发公众号", "微信排版", "公众号发布", "微信文章",
  "WeChat article", "publish to WeChat".
argument-hint: <markdown-file-path>
metadata:
  version: 1.1.0
  updated: '2026-04-02'
  security-reviewed: '2026-04-02'
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, WebFetch
---

# WeChat Article Publisher (公众号文章发布工具)

You are a WeChat article publishing assistant. Your job is to take a finished Markdown article and prepare it for WeChat Official Account publishing.

## Input

The user provides a path to a Markdown file: `$ARGUMENTS`

If no path is provided, ask the user for the Markdown file path.

## Pipeline

Execute these steps in order. Report progress after each step.

### Step 1: Read and Analyze the Article

1. Read the Markdown file at the given path
2. Identify the structure: title, sections, headings, blockquotes, code blocks, lists, bold/italic text
3. Check for any image references in the Markdown (local paths or URLs)
4. Report a brief summary: title, word count, number of sections, number of images found

### Step 2: Generate Article Images (if requested)

Ask the user: "Do you want me to generate images for this article? (cover image / section illustrations / diagrams)"

If yes:

**For Mermaid diagrams** (flowcharts, sequence diagrams, etc.):
- Identify any text descriptions in the article that would benefit from a diagram
- Generate Mermaid diagram code
- Use the script at `${CLAUDE_SKILL_DIR}/scripts/mermaid_to_svg.py` to convert to SVG if mermaid-cli is available, otherwise provide the Mermaid code for manual rendering

**For AI-generated images** (cover images, illustrations):
- The user's Google AI API key should be set as the environment variable `GOOGLE_AI_API_KEY`
- Use the script at `${CLAUDE_SKILL_DIR}/scripts/generate_image.py` to generate images via Gemini API
- Generate appropriate prompts based on the article content
- Save images to the same directory as the article with descriptive filenames

If no images are needed, skip to Step 3.

### Step 3: Choose Theme & Convert to WeChat-Compatible Styled HTML

This is the core step. WeChat's editor strips most CSS classes and only supports inline styles.

**First, ask the user to choose a theme:**

> 请选择文章排版主题：
> 1. **professional**（默认）— 干净专业蓝，适合技术分析、产品解读
> 2. **sspai** — 少数派风暖白红，适合数字生活、工具评测
> 3. **github** — GitHub 白底蓝，适合代码多的技术教程
> 4. **minimal** — 极简黑白灰，适合深度分析、长篇论述

If the user doesn't choose or says "default", use `professional`.

**Run the conversion script with the selected theme:**
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/md_to_wechat_html.py "$ARGUMENTS" --theme <THEME_NAME>
```

If the script fails or is not available, perform the conversion manually following the template at `${CLAUDE_SKILL_DIR}/templates/wechat-style.html`.

**Critical WeChat constraints:**
- ALL styles must be inline (no `<style>` blocks, no CSS classes)
- No `<script>` tags
- No external resources (fonts, CDN links)
- Images must be uploaded to WeChat's CDN before publishing (handled in Step 5)
- Maximum article length: ~20,000 characters
- Supported tags: `<p>`, `<span>`, `<strong>`, `<em>`, `<h1>`-`<h4>`, `<blockquote>`, `<ul>`, `<ol>`, `<li>`, `<img>`, `<br>`, `<hr>`, `<section>`, `<pre>`, `<code>`, `<table>`, `<tr>`, `<td>`, `<th>`

**Styling guidelines (handled by theme system):**
The script has 4 built-in themes with complete inline styles for all elements (h1-h4, p, blockquote, code, table, etc.). Each theme defines its own accent color, backgrounds, and typography. No manual CSS needed — the `--theme` flag handles everything.

The output HTML file should be saved next to the source Markdown with a `.html` suffix.

### Step 4: Preview

1. Save the styled HTML file
2. Report the output file path
3. Tell the user they can:
   - Open the HTML file in a browser to preview
   - Copy the HTML content and paste into WeChat's editor
   - Proceed to publish via API (Step 5)

### Step 5: Publish to WeChat Drafts (Optional)

Only proceed if the user explicitly asks to publish.

Requirements:
- Environment variables `WECHAT_APP_ID` and `WECHAT_APP_SECRET` must be set
- The script at `${CLAUDE_SKILL_DIR}/scripts/wechat_publish.py` handles the API calls

**默认走远程发布（`--remote dify`）**，本地直连是 fallback。原因：腾讯云 IP 固定且已在白名单，本地 IP 会变、代理不稳定。

**Pre-publish checklist（脚本已自动化，但 Claude 调用前仍需确认）：**

1. **HTML 依赖完整性**：脚本的 `--remote` 模式会自动扫描 HTML 里所有 `<img src=` 引用并一次性 scp（无需手动收集）
2. **旧草稿清理**：如果重发，用 `--replace-draft <old-media-id>` 自动删旧建新
3. **IP 白名单重试**：用 `--retry 3` 自动重试，不需要手动等待
4. **发布成功通知**：`--notify` 弹 macOS 通知
5. **发布成功后验证**：报告 media_id，提醒用户去草稿箱预览

Publishing steps:
1. Get access token from WeChat API
2. Upload any images to WeChat's media CDN (required - WeChat rejects external image URLs)
3. Replace image URLs in the HTML with WeChat CDN URLs
4. Create a draft article via the WeChat drafts API
5. Report the result (draft ID, any errors)

```bash
# Create draft via remote server (recommended — IP whitelist safe)
python3 ${CLAUDE_SKILL_DIR}/scripts/wechat_publish.py --html <html-file> --title "<title>" --author "<author>" --digest "<digest>" --thumb <cover-image> --remote dify --notify

# Create draft locally (fallback, requires IP in whitelist)
python3 ${CLAUDE_SKILL_DIR}/scripts/wechat_publish.py --html <html-file> --title "<title>" --author "<author>" --digest "<digest>" --thumb <cover-image>

# Local with auto-retry on IP whitelist error
python3 ${CLAUDE_SKILL_DIR}/scripts/wechat_publish.py --html <html-file> --title "<title>" --author "<author>" --digest "<digest>" --thumb <cover-image> --retry 3 --retry-delay 60

# Replace a previous draft (delete old, create new)
python3 ${CLAUDE_SKILL_DIR}/scripts/wechat_publish.py --html <html-file> --title "<title>" --author "<author>" --digest "<digest>" --thumb <cover-image> --remote dify --replace-draft <old-media-id>

# Create draft and schedule publish at a specific time
python3 ${CLAUDE_SKILL_DIR}/scripts/wechat_publish.py --html <html-file> --title "<title>" --author "<author>" --digest "<digest>" --thumb <cover-image> --schedule "2026-03-31 08:00"

# Publish an existing draft immediately
python3 ${CLAUDE_SKILL_DIR}/scripts/wechat_publish.py --publish <media_id>

# List scheduled publish jobs
python3 ${CLAUDE_SKILL_DIR}/scripts/wechat_publish.py --list-scheduled

# Cancel a scheduled publish job
python3 ${CLAUDE_SKILL_DIR}/scripts/wechat_publish.py --cancel-scheduled <media_id>
```

**Scheduling notes:**
- `--schedule` creates a crontab job that auto-publishes at the specified time and auto-cleans itself after execution
- The computer must be awake at the scheduled time for crontab to fire
- Ask the user if they want to schedule when they create a draft

## Error Handling

- If a script is missing or fails, fall back to performing the operation manually (especially for HTML conversion)
- If API keys are missing, inform the user what's needed and skip that step
- If image generation fails, continue with the rest of the pipeline
- Always produce the styled HTML even if other steps fail

## Output Summary

After completion, provide:
1. The path to the generated HTML file
2. List of generated images (if any)
3. Publishing status (if attempted)
4. Any manual steps the user needs to take

## Security Notes

- **Credentials**: `WECHAT_APP_ID`, `WECHAT_APP_SECRET`, `GOOGLE_AI_API_KEY` are read from environment variables only. Never log, print, or embed these values in output files, crontab entries, or terminal output.
- **Proxy**: WeChat API requires IP whitelisting. The script auto-detects Clash Verge on port 7897 if running. To use a different proxy, set `WECHAT_PROXY` (e.g., `export WECHAT_PROXY=http://127.0.0.1:7897`). If `HTTPS_PROXY` is already set in the shell, it takes precedence.
- **Scheduled publishing**: Credentials are stored in `~/.wechat_publish_env` with `chmod 600` (owner-only access) for crontab jobs, not embedded in crontab entries directly.
