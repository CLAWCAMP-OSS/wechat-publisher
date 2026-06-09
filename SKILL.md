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

**配图密度标准（2026-06-09 Mhao 确认）**：

- **标准档 ≈ 1 张 / 400 字（含封面）**——深度教程/步骤多可上浮到 1/300，纯论述可下沉到 1/500。
- **硬约束（比字数更重要）**：图必须落在「章节转折 / 概念可视化」点位，**宁缺毋滥**。某段没有值得画的概念，就用引用块或表格做视觉呼吸点，**不塞装饰图凑字数**——gpt-image/Gemini 插画堆太满反而拉低质感、拖慢加载。
- **封面不进正文**：封面单独留给公众号封面设置，避免正文与封面重复。
- 落地示例：2660 字文章 → 封面 + 5 张文中图（每章一个概念图），正好踩标准档。

**生成器选择**：默认 Gemini（`GOOGLE_AI_API_KEY`，见下）。也可用 **Codex CLI 生图**（用 Mhao 的 ChatGPT 订阅，效果偏插画）。

**Codex 生图用法 + 4 个 gotcha（2026-06-09 实战沉淀）**：

- **认证**：Codex 的 `~/.codex/auth.json` 是 ChatGPT `tokens` 登录模式即可生图，**不需要 OpenAI API key**（订阅就覆盖生图，API 是单独计费的另一回事——别因为"$20 订阅 ≠ API"就判定不能生图）。
- **调用**：`codex exec --skip-git-repo-check "Use your image generation tool to create ONE image. Do not write or run any code — call the image generation tool exactly once. Image description: <prompt>. ... No text, no numbers. Square 1:1."`（明确"只调一次工具、别写代码、图里别放文字数字"——gpt-image 渲染中文/数字会糊）。
- **输出**：图落在 `~/.codex/generated_images/<新 session>/ig_*.png`，每次 exec 建一个新 session 目录。生成后拷进文章目录。
- ⚠️ **gotcha 1 · 限流**：连发 ~6-7 张后 ChatGPT 订阅生图被节流，codex **挂起 10min+ 不返回**（不是报错，是静默卡死），需冷却 ~30min 才恢复。**批量生图要分批 / 控速**，别一口气连发 7 张以上。
- ⚠️ **gotcha 2 · 定位新图**：`find -newermt "@epoch"` 在后台脚本上下文**不可靠**（2026-06-09 踩过整批误报 FAIL，图其实都生成了只是没拷出来）——改用 `touch <marker>` + `find -newer <marker>`，或按 session 目录 mtime 排序映射。
- ⚠️ **gotcha 3 · macOS 无 `timeout`**：用 `gtimeout`（coreutils）或"后台跑 + poll + kill"，别用 `timeout`（command not found，命令直接没跑）。
- ⚠️ **gotcha 4 · 诊断别丢 `/dev/null`**：调试生图失败时**保留 codex 全输出到日志**，丢 /dev/null 会让你看不到真实失败原因（限流挂起 vs 命令没跑 vs 拷贝逻辑 bug 是三回事，丢输出就全混成"生不出图"）。

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
- ⚠️ **图必须与 md/HTML 平铺同级 + 用 bare 文件名（不放子目录）**：`--remote` 发布时远程 scp 会把所有文件**平铺**到一个临时目录，HTML 里若是 `images/figN.png` 这种**子目录引用，远程找不到 → 文中图全丢**（2026-06-09 踩过，republish 才修好）。命名用 `<article-slug>-figN.png` 平铺在 md 同级目录，对齐 `published/` 历史文章惯例。

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
- 脚本读取顺序：`os.environ` 预设值 > `~/.env.keys` > skill `.env`（凭证唯一真相源是 `~/.env.keys`，2026-06-09 起 skill `.env` 不再存密钥）
- The script at `${CLAUDE_SKILL_DIR}/scripts/wechat_publish.py` handles the API calls

**⚠️ 换/加公众号 mini-checklist（2026-06-09 切号实战）**——切到新号要齐 4 项再发：

1. **AppID + AppSecret**：微信公众平台「设置与开发 → 基本配置」。写进 `~/.env.keys` 的 `WECHAT_APP_ID` / `WECHAT_APP_SECRET`（旧号改名 `WECHAT_OLD_*` 备份别删）。⚠️ 写密钥别在 bash 命令里内嵌 `KEY=值`（hook 会拦）——用 600 临时文件 + 从文件/env 读（见 `env-keys.md`）。
2. **IP 白名单**：新号后台「基本配置 → IP白名单」加 **`--remote` 发布服务器的固定出口公网 IP**（即 `ssh <remote-host>` 那台机的公网 IP；本地直连模式则加你本机出口 IP）。不加 → 取 token 报错码 **40164**。
3. **作者署名**：`--author` 传新号要显示的作者名。
4. **认证前提**：草稿箱 API **只对已认证订阅号/服务号开放**。个人未认证号没有此接口 → 只能用 `_wechat_inner.html` 手动粘贴 + 手动传图。
5. ⚠️ **改了 `~/.env.keys` 当前会话不生效**：shell 快照在会话开始时已 source 旧值 → 要么**开新会话**，要么在发布的同一条命令里 `set -a; source ~/.env.keys; set +a` 显式覆盖（见 `env-keys.md` 的 setdefault 陷阱条）。

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
