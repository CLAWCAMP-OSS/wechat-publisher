# wechat-publisher

> 把 Markdown 一键排版并发布到微信公众号草稿箱。Claude Code skill。

## 功能

- Markdown → 公众号样式 HTML（4 个内置主题：`professional` / `sspai` / `github` / `minimal`）
- 自动用 AI（Google Gemini）生成配图
- 上传到公众号草稿箱（可选定时发布）
- 支持替换已有草稿（避免重复）
- 自带 cron 集成 + 凭证安全管理 + Clash Verge 代理自动检测

## 安装

```bash
# 方式 1: npx skills (推荐)
npx skills add ClawCamp/wechat-publisher

# 方式 2: git clone
git clone https://github.com/ClawCamp/wechat-publisher.git ~/.claude/skills/wechat-publisher
```

## 配置

公众号 API 需要环境变量。**首次运行时 skill 会引导你写入 `~/.wechat_publish_env`（chmod 600）**，无需手动操作。

```bash
WECHAT_APP_ID=wx...           # 公众号 App ID
WECHAT_APP_SECRET=...         # 公众号 App Secret
WECHAT_PROXY=http://...:7897  # 可选，公众号 API 走 IP 白名单时必填
GOOGLE_AI_API_KEY=...         # 可选，用于 AI 生图
```

> 公众号 API 强制 IP 白名单。在白名单 IP 上跑 Clash Verge / 其他代理 → 自动用本地 `127.0.0.1:7897` 中转。

## 使用

直接告诉 Claude：

```
/wechat-publisher article.md
发公众号 article.md
微信排版 article.md
```

Skill 会读你的 Markdown，按模板排版，让你确认配图，最后推到草稿箱。

## 安全

经过 8 维度 security review（OWASP Agentic Top 10 对齐），fix 了：

- 凭证不再写入 crontab（改用 `~/.wechat_publish_env` chmod 600）
- API key 走 HTTP header（不走 URL parameter）
- 代理优先级：`HTTPS_PROXY` > `WECHAT_PROXY` > Clash 自动检测

详见 `SECURITY-REVIEW.md`。

## License

MIT — 见 [LICENSE](LICENSE)。

## 来自

[CLAWCAMP](https://github.com/ClawCamp) · 成人 AI 实战培训
