#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""拉取公众号后台草稿(含 Mhao 在后台逐字手改后的版本),输出可 diff 的段落文本。

用途:Mhao 在公众号后台手改草稿后,拉下来 vs 本地 md 做 diff,提炼写作 lesson。
⚠️ WeChat API 要 IP 白名单 → 本脚本要在已白名单的机器上跑(scp 过去 + ssh,见下).
⚠️ 编辑草稿不改 media_id → 用「创建时返回的 media_id」就能取到「手改后」的内容。
⚠️ wechat_publish.py 没有 get 功能,所以单独这个脚本(2026-06-24 沉淀)。

凭证从环境读(WECHAT_APP_ID / WECHAT_APP_SECRET)。

本地用法(走已白名单的远程机,如 dify):
  ⚠️ 凭证别用 KEY=$(printf %q $VAL) 内嵌进 ssh 命令 —— 那样 secret 会进本地 history
  + 本地/远程进程 argv(远程 ps 可见)。用 600 临时文件传,值不进任何命令文本:
  grep -E '^WECHAT_(APP_ID|APP_SECRET)=' ~/.env.keys > /tmp/wxenv && chmod 600 /tmp/wxenv
  scp -q ~/.claude/skills/wechat-publisher/scripts/fetch_draft.py dify:/tmp/fetch_draft.py
  scp -q /tmp/wxenv dify:/tmp/wxenv
  ssh dify 'chmod 600 /tmp/wxenv; set -a; source /tmp/wxenv; set +a; python3 /tmp/fetch_draft.py <MEDIA_ID>; rm -f /tmp/wxenv /tmp/fetch_draft.py' > /tmp/draft_text.txt
  shred -u /tmp/wxenv 2>/dev/null || rm -f /tmp/wxenv
  # 然后本地: diff <(把本地 md 去 frontmatter/图片/粗体标记后的段落) /tmp/draft_text.txt

参数:
  <media_id>        必填
  --raw             输出完整 JSON(title/digest/content 原始 HTML),默认输出 textify 段落
"""
import os, sys, json, re, html, urllib.request

BASE = "https://api.weixin.qq.com/cgi-bin"


def textify(content_html: str) -> str:
    """WeChat 草稿 content(带内联样式 HTML) → 每段一行的纯文本(可 diff)。"""
    s = re.sub(r"<(p|section|h[1-6]|li|blockquote|figcaption)[^>]*>", "\n", content_html, flags=re.I)
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    paras = [re.sub(r"\s+", " ", p).strip() for p in s.split("\n")]
    return "\n".join(p for p in paras if p and not p.startswith("图片"))


def main():
    args = [a for a in sys.argv[1:] if a != "--raw"]
    raw = "--raw" in sys.argv
    if not args:
        print("usage: fetch_draft.py <media_id> [--raw]", file=sys.stderr); sys.exit(2)
    media_id = args[0]
    app_id = os.environ["WECHAT_APP_ID"]; app_secret = os.environ["WECHAT_APP_SECRET"]

    tok_url = f"{BASE}/token?grant_type=client_credential&appid={app_id}&secret={app_secret}"
    tok = json.loads(urllib.request.urlopen(tok_url, timeout=30).read())
    if "access_token" not in tok:
        print(f"token error: {tok}", file=sys.stderr); sys.exit(3)

    req = urllib.request.Request(
        f"{BASE}/draft/get?access_token={tok['access_token']}",
        data=json.dumps({"media_id": media_id}, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"}, method="POST")
    data = json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8"))
    if "news_item" not in data:
        print(f"draft/get error: {data}", file=sys.stderr); sys.exit(4)

    if raw:
        sys.stdout.write(json.dumps(data, ensure_ascii=False))
    else:
        item = data["news_item"][0]
        sys.stdout.write(f"# {item.get('title','')}\n")
        sys.stdout.write(f"# digest: {item.get('digest','')}\n")
        sys.stdout.write(textify(item.get("content", "")))


if __name__ == "__main__":
    main()
