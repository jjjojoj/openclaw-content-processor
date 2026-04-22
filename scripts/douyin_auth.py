#!/usr/bin/env python3
"""Interactive Douyin auth + media resolution helpers for content-processor."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any


SKILL_DIR = Path(__file__).resolve().parent.parent
AUTH_DIR = SKILL_DIR / "auth" / "douyin"
COOKIES_JSON = AUTH_DIR / "cookies.json"
COOKIES_TXT = AUTH_DIR / "cookies.txt"
STORAGE_STATE = AUTH_DIR / "storage_state.json"
STATE_META = AUTH_DIR / "state.json"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"
)
LOGIN_MARKER_NAMES = {
    "sessionid",
    "sessionid_ss",
    "sid_guard",
    "uid_tt",
    "uid_tt_ss",
    "passport_auth_status",
}
VIDEO_URL_HINTS = (".mp4", ".m3u8", "douyinvod", "playwm", "play_addr")
DETAIL_API_HINTS = ("aweme/detail", "aweme/v1/web/aweme/detail")


def log(message: str) -> None:
    print(f"[douyin-auth] {message}", file=sys.stderr)


def require_playwright():
    try:
        from playwright.sync_api import Error as playwright_error
        from playwright.sync_api import TimeoutError as playwright_timeout_error
        from playwright.sync_api import sync_playwright as sync_playwright_factory
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"缺少 Playwright 运行时: {type(exc).__name__}") from exc
    return sync_playwright_factory, playwright_error, playwright_timeout_error


def ensure_auth_dir() -> None:
    AUTH_DIR.mkdir(parents=True, exist_ok=True)


def command_exists(path: Path) -> bool:
    return path.exists() and path.is_file()


def ensure_playwright_browser() -> None:
    sync_playwright_factory, playwright_error, _ = require_playwright()
    try:
        with sync_playwright_factory() as playwright:
            browser = playwright.chromium.launch(headless=True)
            browser.close()
            return
    except playwright_error as exc:
        message = str(exc)
        if "Executable doesn't exist" not in message and "Please run the following command" not in message:
            raise

    log("Chromium runtime is missing, installing Playwright browser...")
    playwright_bin = Path(sys.executable).with_name("playwright")
    if command_exists(playwright_bin):
        cmd = [str(playwright_bin), "install", "chromium"]
    else:
        cmd = [sys.executable, "-m", "playwright", "install", "chromium"]
    subprocess.run(cmd, check=True)


def normalize_title(title: str) -> str:
    cleaned = (title or "").strip()
    cleaned = re.sub(r"\s*-\s*抖音\s*$", "", cleaned)
    return cleaned.strip()


def normalize_space(text: str) -> str:
    cleaned = (text or "").replace("\r", "\n")
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{2,}", "\n", cleaned)
    return cleaned.strip()


def normalize_douyin_desc_title(text: str) -> str:
    cleaned = normalize_space(text)
    if not cleaned:
        return ""

    for line in cleaned.splitlines():
        candidate = re.sub(r"#\S+", " ", line)
        candidate = re.sub(r"\s+", " ", candidate).strip("“”\"' ").strip()
        sentence_match = re.match(r"^(.+?[。！？!?])(?:\s|$)", candidate)
        if sentence_match:
            candidate = sentence_match.group(1)
        elif len(candidate) > 48 and "，" in candidate:
            parts = [part.strip() for part in candidate.split("，") if part.strip()]
            candidate = "，".join(parts[:2]).rstrip("，")
        candidate = candidate.rstrip("，,、；;：:")
        if candidate:
            return candidate[:80].rstrip()
    return ""


def normalize_douyin_author(author: str, title: str = "") -> str:
    cleaned = normalize_space(author)
    if not cleaned:
        return ""
    cleaned = cleaned.lstrip("@")
    cleaned = cleaned.rstrip("，,、；;：:").strip()
    title_text = normalize_space(title)
    if not cleaned:
        return ""
    if title_text and cleaned == title_text:
        return ""
    if len(cleaned) > 40:
        return ""
    if any(token in cleaned.lower() for token in ["http://", "https://"]):
        return ""
    punctuation_count = sum(cleaned.count(mark) for mark in "，,。！？!?；;")
    if punctuation_count >= 3:
        return ""
    if "#" in cleaned:
        return ""
    return cleaned


def iter_douyin_aweme_items(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []

    candidates: list[dict[str, Any]] = []
    for key in ["aweme_detail", "item_detail", "detail"]:
        value = payload.get(key)
        if isinstance(value, dict):
            candidates.append(value)
    for key in ["aweme_list", "item_list", "aweme_details"]:
        value = payload.get(key)
        if isinstance(value, list):
            candidates.extend(item for item in value if isinstance(item, dict))
    if not candidates and any(key in payload for key in ["desc", "author", "video", "music"]):
        candidates.append(payload)
    return candidates


def extract_douyin_detail_metadata(payload: Any) -> dict[str, str]:
    for aweme in iter_douyin_aweme_items(payload):
        share_info = aweme.get("share_info") if isinstance(aweme.get("share_info"), dict) else {}
        title = normalize_douyin_desc_title(
            str(
                aweme.get("desc")
                or share_info.get("share_title")
                or share_info.get("share_desc")
                or aweme.get("title")
                or ""
            )
        )
        author_obj = aweme.get("author") if isinstance(aweme.get("author"), dict) else {}
        author = normalize_douyin_author(
            str(
                author_obj.get("nickname")
                or author_obj.get("display_id")
                or author_obj.get("unique_id")
                or author_obj.get("short_id")
                or author_obj.get("uid")
                or ""
            ),
            title=title,
        )
        if title or author:
            return {
                "title": title,
                "author": author,
            }
    return {"title": "", "author": ""}


def classify_media_url(url: str) -> str:
    lower = (url or "").lower()
    if not lower.startswith("http"):
        return "other"
    if any(token in lower for token in [".mp4", ".m3u8", "douyinvod", "/aweme/v1/play/", "/play/dash/"]):
        return "video"
    if any(token in lower for token in [".mp3", "ies-music"]):
        return "audio"
    if any(token in lower for token in [".jpeg", ".jpg", ".png", ".webp", "douyinpic.com"]):
        return "image"
    return "other"


def choose_primary_media_url(urls: list[str]) -> str:
    for media_type in ["video", "audio", "other"]:
        for url in urls:
            if classify_media_url(url) == media_type:
                return url
    return urls[0] if urls else ""


def has_login_markers(cookies: list[dict[str, Any]]) -> bool:
    names = {str(cookie.get("name") or "") for cookie in cookies}
    return bool(names & LOGIN_MARKER_NAMES)


def write_netscape_cookie_file(cookies: list[dict[str, Any]], output_path: Path) -> None:
    lines = ["# Netscape HTTP Cookie File"]
    for cookie in cookies:
        name = str(cookie.get("name") or "").strip()
        value = str(cookie.get("value") or "")
        domain = str(cookie.get("domain") or "").strip()
        path = str(cookie.get("path") or "/").strip() or "/"
        if not name or not domain:
            continue
        include_subdomains = "TRUE" if domain.startswith(".") else "FALSE"
        secure = "TRUE" if cookie.get("secure") else "FALSE"
        expires = int(cookie.get("expires") or 0)
        lines.append(
            "\t".join([
                domain,
                include_subdomains,
                path,
                secure,
                str(expires if expires > 0 else 0),
                name,
                value,
            ])
        )
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_cookie_names(cookies: list[dict[str, Any]]) -> list[str]:
    return sorted({str(cookie.get("name") or "") for cookie in cookies if cookie.get("name")})


def save_auth_state(context, page) -> dict[str, Any]:
    ensure_auth_dir()
    cookies = context.cookies()
    context.storage_state(path=str(STORAGE_STATE))
    COOKIES_JSON.write_text(json.dumps(cookies, ensure_ascii=False, indent=2), encoding="utf-8")
    write_netscape_cookie_file(cookies, COOKIES_TXT)
    payload = {
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "cookie_count": len(cookies),
        "cookie_names": load_cookie_names(cookies),
        "has_login_markers": has_login_markers(cookies),
        "current_url": page.url,
        "storage_state": str(STORAGE_STATE),
        "cookies_json": str(COOKIES_JSON),
        "cookies_txt": str(COOKIES_TXT),
    }
    STATE_META.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def load_storage_state_arg() -> str | None:
    return str(STORAGE_STATE) if STORAGE_STATE.exists() else None


def load_cookies_json() -> list[dict[str, Any]]:
    if not COOKIES_JSON.exists():
        return []
    try:
        payload = json.loads(COOKIES_JSON.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return []
    if isinstance(payload, list):
        return [cookie for cookie in payload if isinstance(cookie, dict)]
    return []


def build_context(playwright, headless: bool):
    browser = playwright.chromium.launch(
        headless=headless,
        args=["--disable-blink-features=AutomationControlled"],
    )
    storage_state = load_storage_state_arg()
    context_kwargs = {
        "user_agent": USER_AGENT,
        "viewport": {"width": 1440, "height": 960},
    }
    if storage_state:
        context_kwargs["storage_state"] = storage_state
    context = browser.new_context(**context_kwargs)
    if not storage_state and COOKIES_JSON.exists():
        cookies = load_cookies_json()
        if cookies:
            context.add_cookies(cookies)
    return browser, context


def try_extract_media_urls_from_payload(payload: Any) -> list[str]:
    found: list[str] = []

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            url_list = node.get("url_list")
            if isinstance(url_list, list):
                for value in url_list:
                    if isinstance(value, str) and value.startswith("http"):
                        found.append(value)
            play_addr = node.get("play_addr")
            if isinstance(play_addr, dict):
                visit(play_addr)
            download_addr = node.get("download_addr")
            if isinstance(download_addr, dict):
                visit(download_addr)
            bit_rate = node.get("bit_rate")
            if isinstance(bit_rate, list):
                for value in bit_rate:
                    visit(value)
            for child in node.values():
                visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)

    visit(payload)
    deduped: list[str] = []
    seen: set[str] = set()
    for value in found:
        if value not in seen:
            deduped.append(value)
            seen.add(value)
    return deduped


def run_yt_dlp_url_probe(url: str) -> tuple[list[str], str]:
    ytdlp_bin = SKILL_DIR / ".venv" / "bin" / "yt-dlp"
    if not ytdlp_bin.exists():
        return [], "缺少本地 yt-dlp。"
    if not COOKIES_TXT.exists():
        return [], "没有可用的抖音 cookies.txt。"
    result = subprocess.run(
        [
            str(ytdlp_bin),
            "--ignore-config",
            "--cookies",
            str(COOKIES_TXT),
            "--print",
            "urls",
            "--skip-download",
            url,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    if result.returncode != 0:
        return [], (result.stderr or result.stdout).strip()
    urls = [line.strip() for line in (result.stdout or "").splitlines() if line.strip().startswith("http")]
    return urls, ""


def capture_douyin_media_on_page(page, url: str, wait_seconds: int = 8) -> dict[str, Any]:
    _, _, playwright_timeout_error = require_playwright()

    response_urls: list[str] = []
    detail_payload_urls: list[str] = []
    detail_title = ""
    detail_author = ""
    warnings: list[str] = []

    def handle_response(response) -> None:
        nonlocal detail_title, detail_author
        url_value = response.url
        lower = url_value.lower()
        if any(hint in lower for hint in VIDEO_URL_HINTS):
            response_urls.append(url_value)
        if any(hint in lower for hint in DETAIL_API_HINTS):
            try:
                payload = response.json()
            except Exception:  # noqa: BLE001
                return
            detail_metadata = extract_douyin_detail_metadata(payload)
            if detail_metadata.get("title") and not detail_title:
                detail_title = str(detail_metadata["title"])
            if detail_metadata.get("author") and not detail_author:
                detail_author = str(detail_metadata["author"])
            detail_payload_urls.extend(try_extract_media_urls_from_payload(payload))

    page.on("response", handle_response)

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
    except playwright_timeout_error:
        warnings.append("访问抖音页面超时，继续尝试从已加载内容里解析。")
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "failed",
            "warnings": [f"页面访问失败: {exc}"],
            "media_urls": [],
            "primary_media_url": "",
            "canonical_url": "",
            "title": "",
            "author": "",
        }

    time.sleep(max(1, wait_seconds))

    video_src = ""
    try:
        video_src = page.evaluate(
            """
            () => {
              const video = document.querySelector('video');
              return video ? (video.currentSrc || video.src || '') : '';
            }
            """
        ) or ""
    except Exception:  # noqa: BLE001
        video_src = ""

    title = detail_title or normalize_douyin_desc_title(normalize_title(page.title()))
    author = detail_author
    for selector in [
        '[data-e2e="video-author-nickname"]',
        '[data-e2e="video-author-name"]',
        '[data-e2e="user-info-name"]',
        'h1 span',
    ]:
        if author:
            break
        try:
            value = page.locator(selector).first.text_content(timeout=1200) or ""
        except Exception:  # noqa: BLE001
            value = ""
        value = normalize_douyin_author(value, title=title)
        if value:
            author = value
            break

    if not title:
        for selector in [
            'h1[data-e2e="video-desc"]',
            '[data-e2e="video-desc"]',
            "h1",
        ]:
            try:
                value = page.locator(selector).first.text_content(timeout=1200) or ""
            except Exception:  # noqa: BLE001
                value = ""
            value = normalize_douyin_desc_title(value)
            if value:
                title = value
                break

    candidate_urls: list[str] = []
    for collection in [detail_payload_urls, response_urls, [video_src]]:
        for candidate in collection:
            if isinstance(candidate, str) and candidate.startswith("http") and candidate not in candidate_urls:
                candidate_urls.append(candidate)

    return {
        "status": "success" if candidate_urls else "failed",
        "canonical_url": page.url,
        "title": title,
        "author": author,
        "media_urls": candidate_urls,
        "primary_media_url": choose_primary_media_url(candidate_urls),
        "warnings": warnings,
    }


def capture_douyin_media(url: str, wait_seconds: int = 8) -> dict[str, Any]:
    ensure_playwright_browser()
    sync_playwright_factory, _, _ = require_playwright()
    with sync_playwright_factory() as playwright:
        browser, context = build_context(playwright, headless=True)
        page = context.new_page()
        payload = capture_douyin_media_on_page(page, url, wait_seconds=wait_seconds)
        browser.close()
        return payload


def download_from_resolved_media(url: str, output_dir: Path, wait_seconds: int = 8) -> dict[str, Any]:
    ensure_playwright_browser()
    output_dir.mkdir(parents=True, exist_ok=True)
    sync_playwright_factory, _, _ = require_playwright()
    with sync_playwright_factory() as playwright:
        browser, context = build_context(playwright, headless=True)
        page = context.new_page()
        resolved = capture_douyin_media_on_page(page, url, wait_seconds=wait_seconds)
        resolved["downloaded_file"] = ""
        resolved["download_status"] = "failed"

        media_url = str(resolved.get("primary_media_url") or "")
        if not media_url:
            browser.close()
            return resolved

        file_name = re.sub(r"[^\w\u4e00-\u9fff-]+", "_", str(resolved.get("title") or "douyin_media")).strip("_")
        if not file_name:
            file_name = "douyin_media"
        target = output_dir / f"{file_name[:80]}.mp4"

        try:
            response = page.request.get(
                media_url,
                headers={
                    "Referer": str(resolved.get("canonical_url") or "https://www.douyin.com/"),
                    "User-Agent": USER_AGENT,
                },
                timeout=120000,
            )
            if not response.ok:
                resolved.setdefault("warnings", []).append(f"媒体下载失败: HTTP {response.status}")
            else:
                target.write_bytes(response.body())
                resolved["downloaded_file"] = str(target)
                resolved["download_status"] = "success"
        except Exception as exc:  # noqa: BLE001
            resolved.setdefault("warnings", []).append(f"媒体下载失败: {exc}")

        browser.close()
        return resolved


def login_command(timeout_seconds: int, login_url: str) -> int:
    ensure_playwright_browser()
    ensure_auth_dir()
    disable_prompt = os.environ.get("CONTENT_PROCESSOR_DOUYIN_NO_PROMPT", "").lower() in {"1", "true", "yes"}

    sync_playwright_factory, _, _ = require_playwright()
    with sync_playwright_factory() as playwright:
        browser, context = build_context(playwright, headless=False)
        page = context.new_page()
        page.goto(login_url, wait_until="domcontentloaded", timeout=60000)

        log("浏览器已打开，请在页面中扫码登录抖音。")
        log(f"最长等待 {timeout_seconds} 秒；检测到登录态后会自动保存。")

        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            cookies = context.cookies()
            if has_login_markers(cookies):
                payload = save_auth_state(context, page)
                browser.close()
                print(json.dumps({"status": "success", **payload}, ensure_ascii=False, indent=2))
                return 0
            time.sleep(2)

        if sys.stdin.isatty() and not disable_prompt:
            try:
                input("如果你已经完成扫码登录，请按回车保存当前会话；否则 Ctrl+C 取消。")
            except KeyboardInterrupt:
                browser.close()
                print(json.dumps({"status": "cancelled"}, ensure_ascii=False, indent=2))
                return 2
            payload = save_auth_state(context, page)
            browser.close()
            status = "success" if payload["has_login_markers"] else "partial"
            print(json.dumps({"status": status, **payload}, ensure_ascii=False, indent=2))
            return 0 if status == "success" else 2

        browser.close()
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error": "等待扫码登录超时，未检测到稳定登录态。",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2


def status_command() -> int:
    payload = {
        "status": "success",
        "auth_dir": str(AUTH_DIR),
        "storage_state_exists": STORAGE_STATE.exists(),
        "cookies_json_exists": COOKIES_JSON.exists(),
        "cookies_txt_exists": COOKIES_TXT.exists(),
        "state_meta_exists": STATE_META.exists(),
    }
    if STATE_META.exists():
        try:
            payload["saved_state"] = json.loads(STATE_META.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            payload["saved_state"] = None
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def resolve_command(url: str, wait_seconds: int) -> int:
    warnings: list[str] = []
    ytdlp_urls, ytdlp_error = run_yt_dlp_url_probe(url)
    if ytdlp_urls:
        print(
            json.dumps(
                {
                    "status": "success",
                    "source": "yt-dlp",
                    "original_url": url,
                    "primary_media_url": ytdlp_urls[0],
                    "media_urls": ytdlp_urls,
                    "warnings": warnings,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if ytdlp_error:
        warnings.append(f"yt-dlp 解析失败: {ytdlp_error}")

    resolved = capture_douyin_media(url, wait_seconds=wait_seconds)
    resolved["source"] = "playwright-network"
    resolved["original_url"] = url
    resolved["warnings"] = warnings + list(resolved.get("warnings") or [])
    print(json.dumps(resolved, ensure_ascii=False, indent=2))
    return 0 if resolved.get("status") == "success" else 3


def download_command(url: str, output_dir: Path, wait_seconds: int) -> int:
    downloaded = download_from_resolved_media(url, output_dir=output_dir, wait_seconds=wait_seconds)
    print(json.dumps(downloaded, ensure_ascii=False, indent=2))
    return 0 if downloaded.get("download_status") == "success" else 3


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Douyin auth and media helpers for content-processor.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    login_parser = subparsers.add_parser("login", help="Open Chromium and wait for QR login.")
    login_parser.add_argument("--timeout", type=int, default=180, help="Seconds to wait for login.")
    login_parser.add_argument(
        "--login-url",
        default="https://www.douyin.com/?recommend=1",
        help="Landing page used for QR login.",
    )

    status_parser = subparsers.add_parser("status", help="Show saved auth file status.")
    status_parser.set_defaults(no_extra=True)

    resolve_parser = subparsers.add_parser("resolve", help="Resolve the real media URL for a Douyin share link.")
    resolve_parser.add_argument("url", help="Douyin share link or canonical video URL.")
    resolve_parser.add_argument("--wait", type=int, default=8, help="Seconds to wait for network activity.")

    download_parser = subparsers.add_parser("download", help="Download a Douyin video using saved auth.")
    download_parser.add_argument("url", help="Douyin share link or canonical video URL.")
    download_parser.add_argument("--wait", type=int, default=8, help="Seconds to wait for network activity.")
    download_parser.add_argument("--output-dir", type=Path, required=True, help="Directory to save the media file.")

    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "login":
        return login_command(timeout_seconds=args.timeout, login_url=args.login_url)
    if args.command == "status":
        return status_command()
    if args.command == "resolve":
        return resolve_command(url=args.url, wait_seconds=args.wait)
    if args.command == "download":
        return download_command(url=args.url, output_dir=args.output_dir, wait_seconds=args.wait)
    raise SystemExit(2)


if __name__ == "__main__":
    raise SystemExit(main())
