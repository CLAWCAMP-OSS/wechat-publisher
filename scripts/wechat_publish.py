#!/usr/bin/env python3
"""
Publish HTML article to WeChat Official Account as a draft, with optional
scheduled publishing.

Requires environment variables:
    - WECHAT_APP_ID: Your WeChat Official Account App ID
    - WECHAT_APP_SECRET: Your WeChat Official Account App Secret

Usage:
    # Create a draft (local)
    python3 wechat_publish.py --html article.html --title "文章标题" \
        --author "作者" --digest "摘要" --thumb cover.png

    # Create a draft via remote server (for IP whitelist)
    python3 wechat_publish.py --html article.html --title "文章标题" \
        --author "作者" --digest "摘要" --thumb cover.png --remote dify

    # Auto-retry on IP whitelist error (40164)
    python3 wechat_publish.py --html article.html --title "文章标题" \
        --author "作者" --digest "摘要" --thumb cover.png --retry 3

    # Replace a previous draft (delete old, create new)
    python3 wechat_publish.py --html article.html --title "文章标题" \
        --author "作者" --digest "摘要" --thumb cover.png \
        --replace-draft OLD_MEDIA_ID

    # Create a draft and schedule publish at a specific time
    python3 wechat_publish.py --html article.html --title "文章标题" \
        --author "作者" --digest "摘要" --thumb cover.png \
        --schedule "2026-03-31 08:00"

    # Publish an existing draft immediately
    python3 wechat_publish.py --publish MEDIA_ID

    # List scheduled publish jobs
    python3 wechat_publish.py --list-scheduled

    # Cancel a scheduled publish job
    python3 wechat_publish.py --cancel-scheduled MEDIA_ID
"""

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

# Auto-load .env from skill directory
_skill_env = Path(__file__).resolve().parent.parent / ".env"
if _skill_env.exists():
    for line in _skill_env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


# Proxy for WeChat API requests.
# WeChat Official Account API enforces an IP whitelist — requests from
# non-whitelisted IPs are rejected.  A local proxy (e.g. Clash Verge on
# port 7897) can route traffic through a whitelisted server.
#
# Resolution order:
#   1. HTTPS_PROXY / HTTP_PROXY already set by the shell  → use as-is
#   2. WECHAT_PROXY env var                                → use that
#   3. Clash Verge default (http://127.0.0.1:7897)         → auto-detect
#   4. None of the above                                   → no proxy (direct)
_CLASH_DEFAULT = "http://127.0.0.1:7897"

if not os.environ.get("HTTPS_PROXY") and not os.environ.get("https_proxy"):
    _proxy = os.environ.get("WECHAT_PROXY")
    if not _proxy:
        # Auto-detect: only use Clash default if the port is actually listening
        import socket
        _sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            _sock.settimeout(0.3)
            _sock.connect(("127.0.0.1", 7897))
            _proxy = _CLASH_DEFAULT
        except (ConnectionRefusedError, OSError):
            _proxy = None
        finally:
            _sock.close()
    if _proxy:
        os.environ["HTTPS_PROXY"] = _proxy
        os.environ["HTTP_PROXY"] = _proxy

WECHAT_API_BASE = "https://api.weixin.qq.com/cgi-bin"
SCRIPT_PATH = os.path.abspath(__file__)

# IP whitelist error code from WeChat API
ERR_IP_NOT_IN_WHITELIST = 40164


def get_access_token(app_id: str, app_secret: str) -> str:
    """Get access token from WeChat API."""
    url = (
        f"{WECHAT_API_BASE}/token?"
        f"grant_type=client_credential&appid={app_id}&secret={app_secret}"
    )
    with urllib.request.urlopen(url, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    if "access_token" in data:
        print(f"Access token obtained (expires in {data['expires_in']}s)")
        return data["access_token"]
    elif data.get("errcode") == ERR_IP_NOT_IN_WHITELIST:
        raise IPWhitelistError(data)
    else:
        raise RuntimeError(f"Failed to get access token: {data}")


class IPWhitelistError(RuntimeError):
    """Raised when the request IP is not in WeChat's whitelist."""
    def __init__(self, data: dict):
        self.data = data
        super().__init__(f"IP not in whitelist: {data}")


def upload_image(access_token: str, image_path: str) -> str:
    """Upload an image to WeChat's media CDN and return the URL."""
    url = (
        f"{WECHAT_API_BASE}/media/uploadimg?"
        f"access_token={access_token}"
    )

    image_path = Path(image_path)
    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    # Determine content type
    suffix = image_path.suffix.lower()
    content_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
    }
    content_type = content_types.get(suffix, "image/png")

    # Build multipart form data
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="media"; filename="{image_path.name}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n"
    ).encode("utf-8")
    body += image_path.read_bytes()
    body += f"\r\n--{boundary}--\r\n".encode("utf-8")

    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    if "url" in data:
        print(f"Uploaded {image_path.name} -> {data['url'][:80]}...")
        return data["url"]
    else:
        raise RuntimeError(f"Failed to upload image: {data}")


def upload_thumb(access_token: str, image_path: str) -> str:
    """Upload a thumb image and return the media_id."""
    url = (
        f"{WECHAT_API_BASE}/material/add_material?"
        f"access_token={access_token}&type=thumb"
    )

    image_path = Path(image_path)
    suffix = image_path.suffix.lower()
    content_types = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}
    content_type = content_types.get(suffix, "image/jpeg")

    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="media"; filename="{image_path.name}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n"
    ).encode("utf-8")
    body += image_path.read_bytes()
    body += f"\r\n--{boundary}--\r\n".encode("utf-8")

    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    if "media_id" in data:
        print(f"Thumb uploaded: {data['media_id']}")
        return data["media_id"]
    else:
        raise RuntimeError(f"Failed to upload thumb: {data}")


def fix_list_newlines(html_content: str) -> str:
    """Remove newlines between list tags to prevent WeChat from rendering empty list items."""
    html_content = re.sub(r'(<[uo]l[^>]*>)\s*(<li)', r'\1\2', html_content)
    html_content = re.sub(r'(</li>)\s*(<li)', r'\1\2', html_content)
    html_content = re.sub(r'(</li>)\s*(</[uo]l>)', r'\1\2', html_content)
    return html_content


def replace_local_images(html_content: str, access_token: str, base_dir: Path) -> str:
    """Find local image references in HTML and replace with WeChat CDN URLs."""
    img_pattern = re.compile(r'<img\s+[^>]*src="([^"]+)"', re.IGNORECASE)

    def replace_match(match):
        src = match.group(1)
        # Skip if already a WeChat URL or http(s) URL
        if src.startswith("http://") or src.startswith("https://"):
            # For non-WeChat URLs, try to download and re-upload
            if "mmbiz.qpic.cn" in src:
                return match.group(0)  # Already a WeChat URL
            # Skip external URLs for now (WeChat will reject them)
            print(f"Warning: External image URL will be rejected by WeChat: {src[:60]}...")
            return match.group(0)

        # Local file path
        img_path = base_dir / src
        if not img_path.exists():
            print(f"Warning: Image not found: {img_path}")
            return match.group(0)

        try:
            wechat_url = upload_image(access_token, str(img_path))
            return match.group(0).replace(src, wechat_url)
        except Exception as e:
            print(f"Warning: Failed to upload {src}: {e}")
            return match.group(0)

    return img_pattern.sub(replace_match, html_content)


def scan_html_dependencies(html_path: Path) -> list[Path]:
    """Scan HTML for all local image references and return their file paths."""
    html_content = html_path.read_text(encoding="utf-8")
    img_pattern = re.compile(r'<img\s+[^>]*src="([^"]+)"', re.IGNORECASE)
    base_dir = html_path.parent
    deps = []
    for match in img_pattern.finditer(html_content):
        src = match.group(1)
        if src.startswith("http://") or src.startswith("https://"):
            continue
        img_path = base_dir / src
        if img_path.exists():
            deps.append(img_path)
        else:
            print(f"Warning: Referenced image not found locally: {img_path}")
    return deps


def delete_draft(access_token: str, media_id: str) -> bool:
    """Delete a draft by media_id. Returns True on success."""
    url = f"{WECHAT_API_BASE}/draft/delete?access_token={access_token}"
    payload = json.dumps({"media_id": media_id}).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if data.get("errcode", 0) == 0:
        print(f"Deleted old draft: {media_id}")
        return True
    else:
        print(f"Warning: Failed to delete draft {media_id}: {data}")
        return False


def notify_success(title: str, media_id: str):
    """Send macOS notification on successful publish. No-op on non-macOS."""
    if sys.platform != "darwin":
        return
    msg = f"草稿已创建: {title}\\nMedia ID: {media_id[:40]}..."
    subprocess.run(
        ["osascript", "-e",
         f'display notification "{msg}" with title "微信发布成功" sound name "Glass"'],
        capture_output=True,
    )


def remote_publish(ssh_host: str, args: argparse.Namespace):
    """Execute the publish on a remote server via SSH.

    Automatically:
    1. Scans HTML for all image dependencies
    2. scp's all files (HTML + thumb + inline images + this script) to remote
    3. Runs the publish command via SSH with env vars
    4. Cleans up remote temp dir
    """
    html_path = Path(args.html).resolve()
    if not html_path.exists():
        print(f"Error: HTML file not found: {html_path}")
        sys.exit(1)

    # Collect all files to transfer
    files_to_send = [html_path, Path(SCRIPT_PATH)]
    if args.thumb:
        thumb_path = Path(args.thumb).resolve()
        if thumb_path.exists():
            files_to_send.append(thumb_path)
        else:
            print(f"Error: Thumb file not found: {thumb_path}")
            sys.exit(1)

    # Scan HTML for inline image dependencies
    inline_images = scan_html_dependencies(html_path)
    files_to_send.extend(inline_images)

    # Deduplicate
    files_to_send = list(dict.fromkeys(files_to_send))

    print(f"Remote publish via {ssh_host}")
    print(f"  Files to transfer: {len(files_to_send)}")
    for f in files_to_send:
        print(f"    {f.name} ({f.stat().st_size // 1024}KB)")

    remote_dir = "/tmp/wechat-publish"

    # Create remote dir + scp all files
    subprocess.run(["ssh", ssh_host, f"mkdir -p {remote_dir}"], check=True)
    scp_args = ["scp"] + [str(f) for f in files_to_send] + [f"{ssh_host}:{remote_dir}/"]
    subprocess.run(scp_args, check=True)
    print("  All files transferred.")

    # Build remote command — forward env vars via SSH, not embedding values
    app_id = os.environ.get("WECHAT_APP_ID", "")
    app_secret = os.environ.get("WECHAT_APP_SECRET", "")
    if not app_id or not app_secret:
        print("Error: WECHAT_APP_ID and WECHAT_APP_SECRET required")
        sys.exit(1)

    remote_args = [
        f"--html {shlex.quote(html_path.name)}",
        f"--title {shlex.quote(args.title)}",
    ]
    if args.author:
        remote_args.append(f"--author {shlex.quote(args.author)}")
    if args.digest:
        remote_args.append(f"--digest {shlex.quote(args.digest)}")
    if args.thumb:
        remote_args.append(f"--thumb {shlex.quote(Path(args.thumb).name)}")
    if args.replace_draft:
        remote_args.append(f"--replace-draft {shlex.quote(args.replace_draft)}")
    if args.schedule:
        remote_args.append(f"--schedule {shlex.quote(args.schedule)}")
    if args.retry > 0:
        remote_args.append(f"--retry {args.retry}")
        remote_args.append(f"--retry_delay {args.retry_delay}")
    if args.notify:
        remote_args.append("--notify")

    remote_cmd = (
        f"cd {remote_dir} && "
        f"WECHAT_APP_ID={shlex.quote(app_id)} "
        f"WECHAT_APP_SECRET={shlex.quote(app_secret)} "
        f"python3 wechat_publish.py {' '.join(remote_args)}"
    )

    print("  Executing on remote...")
    result = subprocess.run(["ssh", ssh_host, remote_cmd], capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    # Cleanup remote temp dir
    subprocess.run(["ssh", ssh_host, f"rm -rf {remote_dir}"], capture_output=True)
    print("  Remote temp dir cleaned up.")

    if result.returncode != 0:
        sys.exit(result.returncode)

    # If --notify was requested, also notify locally (remote notification only works on remote)
    if args.notify:
        # Extract media_id from remote output
        for line in result.stdout.splitlines():
            if "Media ID:" in line:
                mid = line.split("Media ID:")[-1].strip()
                notify_success(args.title, mid)
                break


def publish_draft(access_token: str, media_id: str) -> dict:
    """Publish a draft article on WeChat."""
    url = f"{WECHAT_API_BASE}/freepublish/submit?access_token={access_token}"

    payload = {"media_id": media_id}

    req = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    if data.get("errcode", 0) == 0:
        print(f"Publish submitted! Publish ID: {data.get('publish_id', 'N/A')}")
        return data
    else:
        raise RuntimeError(f"Failed to publish: {data}")


def create_draft(
    access_token: str,
    title: str,
    content: str,
    author: str = "",
    digest: str = "",
    thumb_media_id: str = "",
) -> dict:
    """Create a draft article on WeChat."""
    url = f"{WECHAT_API_BASE}/draft/add?access_token={access_token}"

    article = {
        "title": title,
        "author": author,
        "digest": digest,
        "content": content,
        "content_source_url": "",
        "need_open_comment": 0,
        "only_fans_can_comment": 0,
    }

    if thumb_media_id:
        article["thumb_media_id"] = thumb_media_id

    payload = {"articles": [article]}

    req = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    if "media_id" in data:
        print(f"Draft created successfully! Media ID: {data['media_id']}")
        return data
    else:
        raise RuntimeError(f"Failed to create draft: {data}")


# --- Scheduled publishing via crontab ---

CRON_TAG = "# wechat-scheduled-publish:"


def schedule_publish(media_id: str, schedule_time: str, app_id: str, app_secret: str):
    """Schedule a draft to be published at a specific time via crontab.

    Args:
        media_id: The draft media_id to publish.
        schedule_time: Time string in format "YYYY-MM-DD HH:MM".
        app_id: WeChat App ID.
        app_secret: WeChat App Secret.
    """
    dt = datetime.strptime(schedule_time, "%Y-%m-%d %H:%M")

    if dt <= datetime.now():
        print(f"Error: Scheduled time {schedule_time} is in the past.")
        sys.exit(1)

    # Find python3 path
    python_path = sys.executable

    # Write credentials to a secured env file instead of embedding in crontab.
    # Also persist WECHAT_PROXY if the user set it, so the cron job can use it.
    env_file = Path.home() / ".wechat_publish_env"
    env_lines = [
        f"WECHAT_APP_ID={app_id}",
        f"WECHAT_APP_SECRET={app_secret}",
    ]
    wechat_proxy = os.environ.get("WECHAT_PROXY", "")
    if wechat_proxy:
        env_lines.append(f"WECHAT_PROXY={wechat_proxy}")
    env_file.write_text("\n".join(env_lines) + "\n", encoding="utf-8")
    env_file.chmod(0o600)  # Owner-only read/write

    # Build the cron command: source env file, publish, then auto-remove itself.
    # The script auto-detects Clash proxy on port 7897 at startup if no
    # WECHAT_PROXY is set, so the cron job works whether Clash is running or not.
    cron_cmd = (
        f"set -a && . {env_file} && set +a && "
        f"{python_path} {SCRIPT_PATH} --html dummy --title dummy --publish {media_id} "
        f">> /tmp/wechat_publish.log 2>&1 "
        f"&& {python_path} {SCRIPT_PATH} --cancel-scheduled {media_id}"
    )

    cron_expr = f"{dt.minute} {dt.hour} {dt.day} {dt.month} *"
    cron_line = f"{cron_expr} {cron_cmd} {CRON_TAG}{media_id}"

    # Read existing crontab, remove any existing job for this media_id, add new one
    existing = subprocess.run(
        ["crontab", "-l"], capture_output=True, text=True
    ).stdout
    lines = [l for l in existing.strip().split("\n") if l and f"{CRON_TAG}{media_id}" not in l]
    lines.append(cron_line)

    proc = subprocess.run(
        ["crontab", "-"], input="\n".join(lines) + "\n", capture_output=True, text=True
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Failed to update crontab: {proc.stderr}")

    print(f"Scheduled publish for {schedule_time}")
    print(f"  Media ID: {media_id}")
    print(f"  Cron: {cron_expr}")
    print(f"  The job will auto-remove itself after publishing.")
    print(f"  Note: Your computer must be awake at the scheduled time.")


def list_scheduled():
    """List all scheduled WeChat publish jobs."""
    existing = subprocess.run(
        ["crontab", "-l"], capture_output=True, text=True
    ).stdout

    jobs = [l for l in existing.strip().split("\n") if CRON_TAG in l]
    if not jobs:
        print("No scheduled publish jobs found.")
        return

    print(f"Found {len(jobs)} scheduled publish job(s):\n")
    for job in jobs:
        # Extract media_id from tag
        tag_idx = job.index(CRON_TAG)
        media_id = job[tag_idx + len(CRON_TAG):]
        # Extract cron time
        parts = job.split()
        minute, hour, day, month = parts[0], parts[1], parts[2], parts[3]
        print(f"  Time: {month}-{day} {hour}:{minute}")
        print(f"  Media ID: {media_id}")
        print()


def cancel_scheduled(media_id: str):
    """Cancel a scheduled publish job by media_id."""
    existing = subprocess.run(
        ["crontab", "-l"], capture_output=True, text=True
    ).stdout

    lines = existing.strip().split("\n")
    new_lines = [l for l in lines if l and f"{CRON_TAG}{media_id}" not in l]

    if len(new_lines) == len([l for l in lines if l]):
        print(f"No scheduled job found for media_id: {media_id}")
        return

    proc = subprocess.run(
        ["crontab", "-"], input="\n".join(new_lines) + "\n", capture_output=True, text=True
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Failed to update crontab: {proc.stderr}")

    print(f"Cancelled scheduled publish for media_id: {media_id}")


def run_local_publish(args, app_id: str, app_secret: str):
    """Run the publish pipeline locally."""
    html_path = Path(args.html)
    if not html_path.exists():
        print(f"Error: HTML file not found: {html_path}")
        sys.exit(1)

    html_content = html_path.read_text(encoding="utf-8")

    preview_match = re.search(
        r'<div class="wechat-preview">(.*?)</div>\s*</body>',
        html_content,
        re.DOTALL,
    )
    if preview_match:
        html_content = preview_match.group(1).strip()

    html_content = fix_list_newlines(html_content)

    print("Step 1: Getting access token...")
    token = get_access_token(app_id, app_secret)

    # Delete old draft if --replace-draft specified
    if args.replace_draft:
        print(f"Step 1.5: Deleting old draft {args.replace_draft}...")
        delete_draft(token, args.replace_draft)

    print("Step 2: Uploading images...")
    html_content = replace_local_images(html_content, token, html_path.parent)

    thumb_media_id = ""
    if args.thumb:
        print("Step 3: Uploading cover image...")
        thumb_media_id = upload_thumb(token, args.thumb)
    else:
        print("Step 3: No cover image specified, skipping...")

    print("Step 4: Creating draft...")
    result = create_draft(
        access_token=token,
        title=args.title,
        content=html_content,
        author=args.author,
        digest=args.digest,
        thumb_media_id=thumb_media_id,
    )

    draft_media_id = result.get("media_id", "")

    if args.schedule and draft_media_id:
        print(f"\nStep 5: Scheduling publish at {args.schedule}...")
        schedule_publish(draft_media_id, args.schedule, app_id, app_secret)
    else:
        print("\nDraft created!")
        print(f"  Draft Media ID: {draft_media_id}")
        print("  You can now preview and publish the draft in the WeChat Official Account backend.")

    if args.notify and draft_media_id:
        notify_success(args.title, draft_media_id)

    return draft_media_id


def main():
    parser = argparse.ArgumentParser(description="Publish article to WeChat drafts")
    parser.add_argument("--html", default="", help="Path to HTML file")
    parser.add_argument("--title", default="", help="Article title")
    parser.add_argument("--author", default="", help="Author name")
    parser.add_argument("--digest", default="", help="Article digest/summary")
    parser.add_argument("--thumb", default="", help="Path to cover image (thumbnail)")
    parser.add_argument("--publish", default="", help="Publish an existing draft by media_id (skips draft creation)")
    parser.add_argument("--schedule", default="", help="Schedule publish time, format: 'YYYY-MM-DD HH:MM'")
    parser.add_argument("--list-scheduled", action="store_true", help="List all scheduled publish jobs")
    parser.add_argument("--cancel-scheduled", default="", help="Cancel a scheduled publish job by media_id")
    parser.add_argument("--remote", default="", help="SSH host to execute publish on (for IP whitelist bypass)")
    parser.add_argument("--retry", type=int, default=0, help="Number of retries on IP whitelist error (40164)")
    parser.add_argument("--retry-delay", type=int, default=60, dest="retry_delay", help="Seconds between retries (default: 60)")
    parser.add_argument("--replace-draft", default="", dest="replace_draft", help="Delete this draft media_id before creating a new one")
    parser.add_argument("--notify", action="store_true", help="Send macOS notification on success")
    args = parser.parse_args()

    # List scheduled jobs (no credentials needed)
    if args.list_scheduled:
        list_scheduled()
        return

    # Cancel scheduled job (no credentials needed)
    if args.cancel_scheduled:
        cancel_scheduled(args.cancel_scheduled)
        return

    app_id = os.environ.get("WECHAT_APP_ID")
    app_secret = os.environ.get("WECHAT_APP_SECRET")

    if not app_id or not app_secret:
        print("Error: WECHAT_APP_ID and WECHAT_APP_SECRET environment variables are required")
        print("Set them with:")
        print("  export WECHAT_APP_ID='your-app-id'")
        print("  export WECHAT_APP_SECRET='your-app-secret'")
        sys.exit(1)

    # Publish mode: publish an existing draft by media_id
    if args.publish:
        print("Getting access token...")
        token = get_access_token(app_id, app_secret)
        print(f"Publishing draft {args.publish}...")
        result = publish_draft(token, args.publish)
        print("\nPublish submitted!")
        print(f"  Publish ID: {result.get('publish_id', 'N/A')}")
        return

    # Draft creation mode requires --html and --title
    if not args.html or not args.title:
        parser.error("--html and --title are required for creating a draft")

    # Remote mode: delegate to remote server
    if args.remote:
        remote_publish(args.remote, args)
        return

    # Local mode with retry logic
    max_attempts = 1 + args.retry
    for attempt in range(1, max_attempts + 1):
        try:
            run_local_publish(args, app_id, app_secret)
            return
        except IPWhitelistError as e:
            if attempt < max_attempts:
                print(f"\nIP whitelist error (attempt {attempt}/{max_attempts}). "
                      f"Retrying in {args.retry_delay}s...")
                time.sleep(args.retry_delay)
            else:
                print(f"\nIP whitelist error after {max_attempts} attempts.")
                print(f"  {e.data}")
                print(f"\nTip: Use --remote <ssh-host> to publish via a whitelisted server.")
                sys.exit(1)


if __name__ == "__main__":
    main()
