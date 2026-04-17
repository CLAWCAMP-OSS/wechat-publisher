# Security Review Log: wechat-publisher

## Review Date: 2026-04-02

### Reviewer: Claude Opus 4.6 + User
### Framework: 8-Dimension Model (OWASP Agentic Top 10 aligned)

---

## Findings & Fixes

### 1. [CRITICAL] Crontab Credential Exposure — FIXED
- **File**: `scripts/wechat_publish.py:284-285`
- **Issue**: `WECHAT_APP_ID` and `WECHAT_APP_SECRET` were written as plaintext into crontab entries, readable by any process with `crontab -l` access.
- **Fix**: Credentials now stored in `~/.wechat_publish_env` with `chmod 600`. Crontab sources this file at runtime.
- **OWASP**: ASI03 (Identity & Privilege Abuse)

### 2. [CRITICAL] API Key in URL Parameter — FIXED
- **File**: `scripts/generate_image.py:35`
- **Issue**: `GOOGLE_AI_API_KEY` passed as `?key=` URL parameter, exposable in proxy logs, browser history, server logs.
- **Fix**: Changed to `x-goog-api-key` HTTP header authentication.
- **OWASP**: ASI03 (Identity & Privilege Abuse)

### 3. [WARNING] Hardcoded Proxy — FIXED
- **File**: `scripts/wechat_publish.py:43-46`
- **Issue**: Unconditionally set `HTTP_PROXY=http://127.0.0.1:7897` (Clash Verge), which could cause connection failures or unintended traffic routing in other environments.
- **Context**: WeChat API enforces IP whitelist — a proxy to a whitelisted server is functionally required.
- **Fix**: 3-tier resolution: (1) respect existing `HTTPS_PROXY` from shell, (2) use `WECHAT_PROXY` env var if set, (3) auto-detect Clash on port 7897 via socket probe, (4) no proxy if none available. Cron jobs also persist `WECHAT_PROXY` into the secured env file.
- **OWASP**: ASI02 (Tool Misuse)

### 4. [INFO] Name Mismatch — FIXED
- **Issue**: Frontmatter `name: wechat-publish` didn't match directory name `wechat-publisher`.
- **Fix**: Unified to `wechat-publisher`.

### 5. [INFO] Missing Version — FIXED
- **Issue**: No version number in frontmatter.
- **Fix**: Added `version: 1.1.0` and `security-reviewed: 2026-04-02`.

### 6. [INFO] Missing Chinese Trigger Words — FIXED
- **Issue**: Description lacked Chinese keywords for triggering.
- **Fix**: Added "发公众号", "微信排版", "公众号发布", "微信文章".

---

## Remaining Considerations

- `network + shell` permission combination is inherent to this skill's purpose (publishing to WeChat API). Accepted as necessary.
- `disable-model-invocation: true` was removed since the skill has interactive steps ("ask the user").
- Access token is not printed to terminal but expiration time is logged — acceptable.

## Verdict: SAFE (after fixes)
