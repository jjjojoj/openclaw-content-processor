#!/usr/bin/env python3
"""Process one or more share links and build a desktop summary report."""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
from dataclasses import dataclass, field
from datetime import datetime
from html import unescape
from http.cookiejar import MozillaCookieJar
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse
from urllib.request import Request, urlopen

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"
)
SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_ROOT = Path.home() / "Desktop" / "内容摘要"
REPORT_SCHEMA_VERSION = "1.0.0"
ANALYSIS_TEXT_CHAR_LIMIT = 12000
ANALYSIS_SENTENCE_LIMIT = 200
GITHUB_API_BASE = os.environ.get("CONTENT_PROCESSOR_GITHUB_API_BASE", "https://api.github.com").rstrip("/")
DEFAULT_ANALYSIS_MODEL = os.environ.get("CONTENT_PROCESSOR_ANALYSIS_MODEL", "gpt-5-mini")
URL_RE = re.compile(r"https?://[^\s<>\"]+")
SCRAPLING_DYNAMIC_PLATFORMS = {
    "wechat", "toutiao", "xiaohongshu", "weibo", "zhihu", "csdn", "x"
}
SCRAPLING_MODE_MAP = {
    "wechat": ["stealthy-fetch", "fetch", "get"],
    "toutiao": ["stealthy-fetch", "fetch", "get"],
    "xiaohongshu": ["stealthy-fetch", "fetch", "get"],
    "weibo": ["stealthy-fetch", "fetch", "get"],
    "zhihu": ["fetch", "get"],
    "csdn": ["fetch", "get"],
    "x": ["stealthy-fetch", "fetch", "get"],
    "web": ["get"],
}
SCRAPLING_SELECTOR_MAP = {
    "wechat": ["#js_content", ".rich_media_content", "article", "main", "body"],
    "toutiao": [".article-content", ".article-body", "article", "main", "body"],
    "xiaohongshu": ["article", "main", "body"],
    "weibo": ["article", "main", "body"],
    "zhihu": [".RichContent-inner", ".Post-RichText", "article", "main", "body"],
    "csdn": ["#article_content", "article", "main", "body"],
    "x": ["article", "main", "body"],
    "web": ["article", "main", "body"],
}
SCRAPLING_ATTEMPT_LIMIT = {
    "wechat": 8,
    "toutiao": 6,
    "xiaohongshu": 6,
    "weibo": 6,
    "zhihu": 6,
    "csdn": 5,
    "x": 6,
    "web": 4,
}
SCRAPLING_MODE_TIMEOUTS = {
    "get": 40,
    "fetch": 45,
    "stealthy-fetch": 60,
}

PLATFORM_LABELS = {
    "youtube": "YouTube",
    "bilibili": "Bilibili",
    "douyin": "抖音",
    "xiaohongshu": "小红书",
    "weibo": "微博",
    "wechat": "微信公众号",
    "zhihu": "知乎",
    "csdn": "CSDN",
    "toutiao": "今日头条",
    "x": "X/Twitter",
    "github": "GitHub",
    "web": "网页",
    "file": "本地文件",
}

STOP_WORDS = {
    "the", "and", "for", "that", "with", "this", "from", "have", "your",
    "will", "into", "about", "http", "https", "www", "com", "you", "they",
    "their", "there", "what", "when", "were", "been", "them", "then", "than",
    "also", "just", "some", "more", "such", "very", "much", "into", "over",
    "music", "upbeat",
    "我们", "你们", "他们", "这个", "那个", "这些", "那些", "一个", "一些", "已经", "因为",
    "所以", "如果", "然后", "就是", "不是", "还有", "可以", "需要", "进行", "内容", "视频",
    "文章", "平台", "用户", "分享", "链接", "今天", "一个", "没有", "自己", "以及", "通过",
    "关于", "其中", "这种", "这次", "起来", "目前", "同时", "开始", "最后", "对于", "相关",
}


@dataclass(slots=True)
class RequestOptions:
    cookie_header: str = ""
    cookies_file: str = ""
    cookies_from_browser: str = ""
    extra_headers: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class AnalysisOptions:
    mode: str = "auto"
    model: str = DEFAULT_ANALYSIS_MODEL
    timeout: int = 60


def normalize_cookie_header(cookie_header: str | None) -> str:
    if not cookie_header:
        return ""
    parts = [
        segment.strip()
        for segment in cookie_header.split(";")
        if segment.strip()
    ]
    return "; ".join(parts)


def parse_header_values(raw_headers: Iterable[str]) -> dict[str, str]:
    headers: dict[str, str] = {}
    for raw in raw_headers:
        if ":" not in raw:
            raise ValueError(f"Invalid header format: {raw!r}. Expected 'Key: Value'.")
        key, value = raw.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            raise ValueError(f"Invalid header format: {raw!r}. Header name is empty.")
        headers[key] = value
    return headers


def resolve_cookie_header(url: str, request_options: RequestOptions) -> str:
    explicit = normalize_cookie_header(request_options.cookie_header)
    if explicit:
        return explicit
    if not request_options.cookies_file:
        return ""

    cookie_file = Path(request_options.cookies_file).expanduser()
    if not cookie_file.exists():
        return ""

    try:
        jar = MozillaCookieJar(str(cookie_file))
        jar.load(ignore_discard=True, ignore_expires=True)
        probe = Request(url)
        jar.add_cookie_header(probe)
        return normalize_cookie_header(probe.get_header("Cookie"))
    except Exception:  # noqa: BLE001
        return ""


def build_request_headers(url: str, request_options: RequestOptions) -> dict[str, str]:
    headers = {"User-Agent": USER_AGENT}
    headers.update(request_options.extra_headers)
    cookie_header = resolve_cookie_header(url, request_options)
    if cookie_header:
        headers["Cookie"] = cookie_header
    return headers


def build_yt_dlp_args(base_args: list[str], request_options: RequestOptions) -> list[str]:
    args = list(base_args)
    if request_options.cookies_file:
        args.extend(["--cookies", str(Path(request_options.cookies_file).expanduser())])
    elif request_options.cookies_from_browser:
        args.extend(["--cookies-from-browser", request_options.cookies_from_browser])

    request_headers = build_request_headers("https://example.com", request_options)
    for key, value in request_headers.items():
        if key.lower() == "user-agent":
            continue
        args.extend(["--add-headers", f"{key}:{value}"])
    return args


def build_scrapling_header_args(
    url: str,
    request_options: RequestOptions,
    flag_name: str,
    include_cookie: bool = True,
) -> list[str]:
    args: list[str] = []
    request_headers = build_request_headers(url, request_options)
    for key, value in request_headers.items():
        if not include_cookie and key.lower() == "cookie":
            continue
        args.extend([flag_name, f"{key}: {value}"])
    return args


def derive_failure_code(warnings: Iterable[str]) -> str:
    normalized = " | ".join(warnings).lower()
    if not normalized:
        return "content_unavailable"
    if "缺少" in normalized or "missing" in normalized:
        return "missing_dependency"
    if "timeout" in normalized or "超时" in normalized:
        return "timeout"
    if "ssl" in normalized or "证书" in normalized:
        return "ssl_error"
    return "extract_failed"


def summarize_item_status(item: dict[str, object]) -> str:
    content = str(item.get("content") or "").strip()
    warnings = list(item.get("warnings") or [])
    if not content:
        return "failed"
    if warnings:
        return "partial"
    return "success"


def build_run_summary(items: list[dict[str, object]]) -> dict[str, int | str]:
    status_counts = {"success": 0, "partial": 0, "failed": 0}
    warning_count = 0
    for item in items:
        status = str(item.get("status") or "failed")
        status_counts[status] = status_counts.get(status, 0) + 1
        warning_count += int(item.get("warning_count") or 0)

    if status_counts["failed"] == len(items):
        overall_status = "failed"
    elif status_counts["failed"] == 0 and status_counts["partial"] == 0:
        overall_status = "success"
    else:
        overall_status = "partial"

    return {
        "status": overall_status,
        "item_count": len(items),
        "success_count": status_counts["success"],
        "partial_count": status_counts["partial"],
        "failed_count": status_counts["failed"],
        "warning_count": warning_count,
    }


def build_tool_info() -> dict[str, object]:
    def run_version(command: list[str]) -> str | None:
        try:
            result = run_command(command, timeout=30)
        except Exception:  # noqa: BLE001
            return None
        if result.returncode != 0:
            return None
        output = normalize_space((result.stdout or result.stderr).splitlines()[0] if (result.stdout or result.stderr) else "")
        return output or None

    scrapling_bin = find_scrapling_bin()
    scrapling_python = str(Path(scrapling_bin).resolve().parent / "python") if scrapling_bin else ""
    scrapling_version = None
    ytdlp_bin = find_ytdlp_bin()
    summarize_bin = find_summarize_bin()
    if scrapling_python and Path(scrapling_python).exists():
        scrapling_version = run_version(
            [
                scrapling_python,
                "-c",
                "import scrapling; print(getattr(scrapling, '__version__', 'unknown'))",
            ]
        )

    return {
        "python": {
            "version": sys.version.split()[0],
            "path": sys.executable,
        },
        "yt_dlp": {
            "version": run_version([ytdlp_bin, "--version"]) if ytdlp_bin else None,
            "path": ytdlp_bin,
        },
        "ffmpeg": {
            "version": run_version(["ffmpeg", "-version"]) if command_exists("ffmpeg") else None,
            "path": shutil.which("ffmpeg"),
        },
        "whisper_cli": {
            "version": run_version(["whisper-cli", "-v"]) if command_exists("whisper-cli") else None,
            "path": shutil.which("whisper-cli"),
        },
        "summarize": {
            "version": run_version([summarize_bin, "--version"]) if summarize_bin else None,
            "path": summarize_bin,
        },
        "scrapling": {
            "version": scrapling_version,
            "path": scrapling_bin,
        },
    }


def run_command(
    args: list[str],
    timeout: int = 120,
    input_text: str | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            args,
            input=input_text,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        message = stderr or stdout or f"Command timed out after {timeout}s"
        return subprocess.CompletedProcess(
            args=args,
            returncode=124,
            stdout=stdout,
            stderr=message,
        )


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def find_preferred_bin(name: str) -> str | None:
    local_bin = SKILL_DIR / ".venv" / "bin" / name
    if local_bin.exists():
        return str(local_bin)
    return shutil.which(name)


def find_ytdlp_bin() -> str | None:
    return find_preferred_bin("yt-dlp")


def find_summarize_bin() -> str | None:
    return find_preferred_bin("summarize")


def import_trafilatura():
    try:
        import trafilatura  # type: ignore[import-not-found]
    except Exception:  # noqa: BLE001
        return None
    return trafilatura


def find_scrapling_bin() -> str | None:
    candidates = [
        os.environ.get("SCRAPLING_BIN"),
        str(SKILL_DIR / ".venv" / "bin" / "scrapling"),
        shutil.which("scrapling"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).expanduser().exists():
            return str(Path(candidate).expanduser())
    return None


def build_scrapling_env(scrapling_bin: str) -> dict[str, str]:
    env = os.environ.copy()
    candidate_paths = []

    local_bundle = next(
        iter((SKILL_DIR / ".venv").glob("lib/python*/site-packages/certifi/cacert.pem")),
        None,
    )
    if local_bundle and local_bundle.exists():
        candidate_paths.append(str(local_bundle))

    bin_path = Path(scrapling_bin).expanduser().resolve()
    sibling_bundle = bin_path.parent.parent / "lib"
    for bundle in sibling_bundle.glob("python*/site-packages/certifi/cacert.pem"):
        if bundle.exists():
            candidate_paths.append(str(bundle))
            break

    for bundle in candidate_paths:
        env["SSL_CERT_FILE"] = bundle
        env["REQUESTS_CA_BUNDLE"] = bundle
        env["CURL_CA_BUNDLE"] = bundle
        break

    return env


def log(message: str) -> None:
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}", file=sys.stderr)


def normalize_space(text: str) -> str:
    text = text.replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def limit_analysis_text(text: str, max_chars: int = ANALYSIS_TEXT_CHAR_LIMIT) -> str:
    normalized = normalize_space(text)
    if len(normalized) <= max_chars:
        return normalized
    clipped = normalized[:max_chars]
    boundary = max(clipped.rfind("\n"), clipped.rfind(" "))
    if boundary >= max_chars // 2:
        return clipped[:boundary].strip()
    return clipped.strip()


def clean_transcript_text(text: str) -> str:
    cleaned = URL_RE.sub(" ", text)
    cleaned = re.sub(
        r"(?i)[\[(][^()\[\]]*(music|applause|laughter|cheering|crowd noise|background music)[^()\[\]]*[\])]",
        " ",
        cleaned,
    )
    cleaned = re.sub(r"(?i)\b(?:music|applause|laughter|cheering)\b", " ", cleaned)
    return normalize_space(cleaned)


def sanitize_filename(text: str, default: str = "report") -> str:
    cleaned = re.sub(r"[^\w\u4e00-\u9fff-]+", "_", text.strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned[:80] or default


def shorten(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def extract_sources(raw_sources: Iterable[str]) -> list[str]:
    sources: list[str] = []
    for raw in raw_sources:
        candidate = raw.strip()
        if not candidate:
            continue
        if Path(candidate).expanduser().exists():
            sources.append(str(Path(candidate).expanduser()))
            continue
        urls = URL_RE.findall(candidate)
        if urls:
            sources.extend(urls)
        else:
            sources.append(candidate)
    deduped: list[str] = []
    seen: set[str] = set()
    for source in sources:
        if source not in seen:
            deduped.append(source)
            seen.add(source)
    return deduped


def classify_source(source: str) -> tuple[str, str]:
    path = Path(source).expanduser()
    if path.exists():
        return "file", path.suffix.lower()

    parsed = urlparse(source)
    host = parsed.netloc.lower()
    path_lower = parsed.path.lower()

    if "youtube.com" in host or "youtu.be" in host:
        return "youtube", "url"
    if "bilibili.com" in host or "b23.tv" in host:
        return "bilibili", "url"
    if "douyin.com" in host or "iesdouyin.com" in host:
        return "douyin", "url"
    if "xiaohongshu.com" in host or "xhslink.com" in host:
        return "xiaohongshu", "url"
    if "weibo.com" in host or "weibo.cn" in host:
        return "weibo", "url"
    if "mp.weixin.qq.com" in host:
        return "wechat", "url"
    if "zhihu.com" in host:
        return "zhihu", "url"
    if "csdn.net" in host:
        return "csdn", "url"
    if "toutiao.com" in host:
        return "toutiao", "url"
    if "x.com" in host or "twitter.com" in host:
        return "x", "url"
    if "github.com" in host or "raw.githubusercontent.com" in host:
        repo_ref = parse_github_source(source)
        if repo_ref and repo_ref.get("kind") in {"repo", "tree", "blob", "raw"}:
            return "github", repo_ref.get("kind", "repo")
        return "github", "url"
    if path_lower.endswith(".pdf"):
        return "web", "pdf"
    return "web", "url"


def html_to_text(html: str) -> str:
    text = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", html)
    text = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", text)
    text = re.sub(r"(?is)<!--.*?-->", " ", text)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p>", "\n", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return normalize_space(text)


def extract_meta_tag(html: str, attr: str, value: str) -> str | None:
    patterns = [
        rf'<meta[^>]+{attr}=["\']{re.escape(value)}["\'][^>]+content=["\'](.*?)["\']',
        rf'<meta[^>]+content=["\'](.*?)["\'][^>]+{attr}=["\']{re.escape(value)}["\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, html, flags=re.IGNORECASE | re.DOTALL)
        if match:
            return normalize_space(unescape(match.group(1)))
    return None


def fetch_html(
    url: str,
    request_options: RequestOptions,
) -> tuple[str | None, dict[str, str], list[str]]:
    warnings: list[str] = []
    metadata: dict[str, str] = {}
    try:
        req = Request(url, headers=build_request_headers(url, request_options))
        with urlopen(req, timeout=30) as response:
            raw = response.read()
            encoding = response.headers.get_content_charset() or "utf-8"
            html = raw.decode(encoding, errors="replace")
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"网页抓取失败: {exc}")
        return None, metadata, warnings

    title = extract_meta_tag(html, "property", "og:title")
    if not title:
        match = re.search(r"(?is)<title>(.*?)</title>", html)
        if match:
            title = normalize_space(unescape(match.group(1)))
    if title:
        metadata["title"] = title

    for attr, value, key in [
        ("name", "author", "author"),
        ("property", "article:author", "author"),
        ("property", "og:site_name", "site_name"),
        ("property", "article:published_time", "published_at"),
        ("name", "description", "description"),
        ("property", "og:description", "description"),
    ]:
        found = extract_meta_tag(html, attr, value)
        if found and key not in metadata:
            metadata[key] = found

    return html, metadata, warnings


def fetch_json_url(
    url: str,
    headers: dict[str, str],
    timeout: int = 30,
) -> tuple[dict[str, object] | list[object] | None, list[str]]:
    try:
        req = Request(url, headers=headers)
        with urlopen(req, timeout=timeout) as response:
            raw = response.read()
            encoding = response.headers.get_content_charset() or "utf-8"
            return json.loads(raw.decode(encoding, errors="replace")), []
    except Exception as exc:  # noqa: BLE001
        return None, [f"JSON 请求失败: {exc}"]


def fetch_text_url(
    url: str,
    headers: dict[str, str],
    timeout: int = 30,
) -> tuple[str | None, list[str]]:
    try:
        req = Request(url, headers=headers)
        with urlopen(req, timeout=timeout) as response:
            raw = response.read()
            encoding = response.headers.get_content_charset() or "utf-8"
            return raw.decode(encoding, errors="replace"), []
    except Exception as exc:  # noqa: BLE001
        return None, [f"文本请求失败: {exc}"]


def parse_github_source(source: str) -> dict[str, str] | None:
    parsed = urlparse(source)
    host = parsed.netloc.lower()
    parts = [part for part in parsed.path.split("/") if part]

    if host == "raw.githubusercontent.com" and len(parts) >= 4:
        return {
            "owner": parts[0],
            "repo": parts[1].removesuffix(".git"),
            "branch": parts[2],
            "path": "/".join(parts[3:]),
            "kind": "raw",
        }

    if "github.com" not in host or len(parts) < 2:
        return None

    owner = parts[0]
    repo = parts[1].removesuffix(".git")
    kind = "repo"
    branch = ""
    file_path = ""
    if len(parts) >= 5 and parts[2] in {"blob", "tree"}:
        kind = parts[2]
        branch = parts[3]
        file_path = "/".join(parts[4:])

    return {
        "owner": owner,
        "repo": repo,
        "branch": branch,
        "path": file_path,
        "kind": kind,
    }


def decode_base64_text(value: str) -> str | None:
    try:
        return base64.b64decode(value).decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return None


def build_github_content(repo_data: dict[str, object], readme_text: str) -> str:
    lines = [
        f"Repository: {repo_data.get('full_name') or ''}",
        f"Description: {repo_data.get('description') or ''}",
        f"Primary language: {repo_data.get('language') or ''}",
        f"Stars: {repo_data.get('stargazers_count') or 0}",
        f"Forks: {repo_data.get('forks_count') or 0}",
        f"Open issues: {repo_data.get('open_issues_count') or 0}",
        f"Topics: {', '.join(repo_data.get('topics') or [])}",
        f"Default branch: {repo_data.get('default_branch') or ''}",
        f"Homepage: {repo_data.get('homepage') or ''}",
        f"Latest update: {repo_data.get('updated_at') or ''}",
        "",
        "README",
        "",
        readme_text.strip(),
    ]
    return normalize_space("\n".join(line for line in lines if line is not None))


def extract_github_repo(
    source: str,
    request_options: RequestOptions,
) -> tuple[dict[str, object], str | None, str | None, list[str]]:
    repo_ref = parse_github_source(source)
    if not repo_ref:
        return {}, None, None, ["无法识别 GitHub 仓库路径。"]

    headers = build_request_headers(source, request_options)
    headers["Accept"] = "application/vnd.github+json"

    owner = repo_ref["owner"]
    repo = repo_ref["repo"]
    repo_url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}"
    repo_payload, repo_warnings = fetch_json_url(repo_url, headers=headers)
    if not isinstance(repo_payload, dict):
        return {}, None, None, repo_warnings or ["GitHub 仓库元数据请求失败。"]

    readme_text = ""
    readme_url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/readme"
    readme_payload, readme_warnings = fetch_json_url(readme_url, headers=headers)
    warnings = list(repo_warnings)
    warnings.extend(readme_warnings)
    if isinstance(readme_payload, dict):
        encoded = str(readme_payload.get("content") or "")
        if encoded and str(readme_payload.get("encoding") or "").lower() == "base64":
            decoded = decode_base64_text(encoded)
            if decoded:
                readme_text = decoded
        if not readme_text and readme_payload.get("download_url"):
            download_headers = build_request_headers(source, request_options)
            raw_text, raw_warnings = fetch_text_url(str(readme_payload["download_url"]), headers=download_headers)
            warnings.extend(raw_warnings)
            readme_text = raw_text or ""

    if not readme_text and repo_ref.get("kind") in {"blob", "raw"} and repo_ref.get("path"):
        branch = repo_ref.get("branch") or str(repo_payload.get("default_branch") or "main")
        raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{repo_ref['path']}"
        raw_headers = build_request_headers(raw_url, request_options)
        raw_text, raw_warnings = fetch_text_url(raw_url, headers=raw_headers)
        warnings.extend(raw_warnings)
        readme_text = raw_text or ""

    content = build_github_content(repo_payload, readme_text or "README unavailable.")
    source_metadata = {
        "full_name": repo_payload.get("full_name") or f"{owner}/{repo}",
        "description": repo_payload.get("description") or "",
        "language": repo_payload.get("language") or "",
        "stargazers_count": repo_payload.get("stargazers_count") or 0,
        "forks_count": repo_payload.get("forks_count") or 0,
        "open_issues_count": repo_payload.get("open_issues_count") or 0,
        "topics": repo_payload.get("topics") or [],
        "homepage": repo_payload.get("homepage") or "",
        "license": (
            repo_payload.get("license", {}).get("spdx_id")
            if isinstance(repo_payload.get("license"), dict)
            else ""
        ),
        "default_branch": repo_payload.get("default_branch") or "",
        "updated_at": repo_payload.get("updated_at") or "",
        "readme_available": bool(readme_text.strip()),
    }
    return source_metadata, content, "github api + readme", warnings


def extract_with_trafilatura(html: str) -> tuple[str | None, list[str]]:
    trafilatura = import_trafilatura()
    if trafilatura is None:
        return None, ["缺少 trafilatura，本地网页抽取不可用。"]
    try:
        text = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=True,
            favor_precision=True,
            output_format="txt",
        )
    except Exception as exc:  # noqa: BLE001
        return None, [f"trafilatura 提取失败: {exc}"]
    normalized = normalize_space(str(text or ""))
    if len(normalized) < 120:
        return None, []
    return normalized, []


def clean_subtitle_text(text: str) -> str:
    cleaned_lines: list[str] = []
    previous = ""
    for line in text.splitlines():
        candidate = line.strip()
        if not candidate:
            continue
        if candidate.startswith("WEBVTT"):
            continue
        if re.match(r"^\d+$", candidate):
            continue
        if "-->" in candidate:
            continue
        if re.match(r"^[\[\(].*[\]\)]$", candidate):
            continue
        candidate = re.sub(r"<[^>]+>", "", candidate)
        candidate = re.sub(r"{\\.*?}", "", candidate)
        candidate = clean_transcript_text(unescape(candidate))
        if not candidate:
            continue
        if candidate != previous:
            cleaned_lines.append(candidate)
            previous = candidate
    return normalize_space("\n".join(cleaned_lines))


def find_whisper_model() -> Path | None:
    candidates = []
    env_model = os.environ.get("WHISPER_MODEL")
    if env_model:
        candidates.append(Path(env_model).expanduser())
    candidates.extend(
        [
            Path.home() / ".whisper-models" / "ggml-small.bin",
            Path.home() / ".whisper-models" / "ggml-base.bin",
            Path("/opt/homebrew/share/whisper/models/ggml-small.bin"),
            Path("/opt/homebrew/share/whisper/models/ggml-base.bin"),
        ]
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def format_duration(seconds: int | float | None) -> str | None:
    if not seconds:
        return None
    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def load_yt_metadata(
    url: str,
    request_options: RequestOptions,
) -> tuple[dict[str, object], list[str]]:
    warnings: list[str] = []
    ytdlp_bin = find_ytdlp_bin()
    if not ytdlp_bin:
        warnings.append("缺少 yt-dlp，无法走多平台媒体提取。")
        return {}, warnings

    result = run_command(build_yt_dlp_args(
        [ytdlp_bin, "--dump-single-json", "--skip-download", "--no-playlist", url],
        request_options,
    ), timeout=180)
    if result.returncode != 0:
        error = normalize_space(result.stderr or result.stdout)
        warnings.append(f"yt-dlp 元数据提取失败: {shorten(error, 160)}")
        return {}, warnings
    try:
        return json.loads(result.stdout), warnings
    except json.JSONDecodeError as exc:
        warnings.append(f"yt-dlp JSON 解析失败: {exc}")
        return {}, warnings


def fetch_yt_subtitles(
    url: str,
    tmpdir: Path,
    request_options: RequestOptions,
) -> tuple[str | None, str | None, list[str]]:
    warnings: list[str] = []
    ytdlp_bin = find_ytdlp_bin()
    if not ytdlp_bin:
        return None, None, ["缺少 yt-dlp，无法下载字幕。"]

    result = run_command(build_yt_dlp_args(
        [
            ytdlp_bin,
            "--skip-download",
            "--no-playlist",
            "--write-subs",
            "--write-auto-subs",
            "--sub-langs",
            "zh.*,zh-Hans,zh-Hant,en.*",
            "--convert-subs",
            "srt",
            "-o",
            str(tmpdir / "media.%(ext)s"),
            url,
        ],
        request_options,
    ), timeout=240)
    if result.returncode != 0:
        error = normalize_space(result.stderr or result.stdout)
        warnings.append(f"字幕抓取失败: {shorten(error, 160)}")

    subtitle_files = sorted(
        [
            path for path in tmpdir.iterdir()
            if path.suffix.lower() in {".srt", ".vtt", ".txt"}
        ],
        key=lambda path: (
            0 if ".zh" in path.name else 1 if ".en" in path.name else 2,
            path.name,
        ),
    )
    for file_path in subtitle_files:
        text = clean_subtitle_text(file_path.read_text(encoding="utf-8", errors="replace"))
        if len(text) >= 120:
            return text, f"yt-dlp subtitles ({file_path.name})", warnings
    return None, None, warnings


def transcribe_with_whisper(media_path: Path, tmpdir: Path) -> tuple[str | None, list[str]]:
    warnings: list[str] = []
    if not command_exists("ffmpeg"):
        return None, ["缺少 ffmpeg，无法转写音视频。"]
    if not command_exists("whisper-cli"):
        return None, ["缺少 whisper-cli，无法转写音视频。"]

    model = find_whisper_model()
    if model is None:
        return None, ["缺少 Whisper 模型文件，无法转写音视频。"]

    wav_path = tmpdir / "transcribe.wav"
    ffmpeg_result = run_command(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(media_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            str(wav_path),
        ],
        timeout=600,
    )
    if ffmpeg_result.returncode != 0:
        error = normalize_space(ffmpeg_result.stderr or ffmpeg_result.stdout)
        return None, [f"ffmpeg 转码失败: {shorten(error, 160)}"]

    out_base = tmpdir / "transcript"
    whisper_result = run_command(
        [
            "whisper-cli",
            "-m",
            str(model),
            "-l",
            "auto",
            "-otxt",
            "-of",
            str(out_base),
            str(wav_path),
        ],
        timeout=1200,
    )
    if whisper_result.returncode != 0:
        error = normalize_space(whisper_result.stderr or whisper_result.stdout)
        return None, [f"whisper-cli 转写失败: {shorten(error, 160)}"]

    transcript_path = out_base.with_suffix(".txt")
    if not transcript_path.exists():
        return None, ["whisper-cli 未生成 transcript.txt。"]
    text = clean_transcript_text(transcript_path.read_text(encoding="utf-8", errors="replace"))
    if not text:
        return None, ["转写结果为空。"]
    return text, warnings


def download_media_for_transcription(
    url: str,
    tmpdir: Path,
    request_options: RequestOptions,
) -> tuple[Path | None, list[str]]:
    warnings: list[str] = []
    ytdlp_bin = find_ytdlp_bin()
    if not ytdlp_bin:
        return None, ["缺少 yt-dlp，无法下载媒体文件。"]

    result = run_command(build_yt_dlp_args(
        [
            ytdlp_bin,
            "--no-playlist",
            "-f",
            "bestaudio/best",
            "-o",
            str(tmpdir / "downloaded.%(ext)s"),
            url,
        ],
        request_options,
    ), timeout=900)
    if result.returncode != 0:
        error = normalize_space(result.stderr or result.stdout)
        return None, [f"媒体下载失败: {shorten(error, 160)}"]

    for path in sorted(tmpdir.iterdir()):
        if path.name.startswith("downloaded.") and path.suffix.lower() not in {".part"}:
            return path, warnings
    return None, ["未找到下载后的媒体文件。"]


def extract_with_scrapling(
    url: str,
    platform_key: str,
    request_options: RequestOptions,
) -> tuple[str | None, str | None, list[str]]:
    warnings: list[str] = []
    scrapling_bin = find_scrapling_bin()
    if not scrapling_bin:
        return None, None, [
            "Scrapling 未安装。运行 bash scripts/bootstrap.sh --install-python 可启用动态/反爬页面兜底。"
        ]
    scrapling_env = build_scrapling_env(scrapling_bin)

    modes = SCRAPLING_MODE_MAP.get(platform_key, SCRAPLING_MODE_MAP["web"])
    selectors = SCRAPLING_SELECTOR_MAP.get(platform_key, SCRAPLING_SELECTOR_MAP["web"])
    generic_selectors = [selector for selector in ["article", "main", "body"] if selector in selectors]
    max_attempts = SCRAPLING_ATTEMPT_LIMIT.get(platform_key, SCRAPLING_ATTEMPT_LIMIT["web"])

    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        attempts: list[tuple[str, str | None]] = []
        prioritized_selectors = selectors[:2]
        for selector in generic_selectors:
            if selector not in prioritized_selectors:
                prioritized_selectors.append(selector)
        for selector in selectors:
            if selector not in prioritized_selectors:
                prioritized_selectors.append(selector)
            if len(prioritized_selectors) >= 4:
                break

        if platform_key in SCRAPLING_DYNAMIC_PLATFORMS:
            dynamic_modes = [mode for mode in modes if mode in {"stealthy-fetch", "fetch"}]
            if not dynamic_modes:
                dynamic_modes = modes[:1]
            get_mode = "get" if "get" in modes else modes[-1]
            for selector in prioritized_selectors[:2]:
                for mode in dynamic_modes[:2]:
                    attempts.append((mode, selector))
            for selector in prioritized_selectors:
                attempts.append((get_mode, selector))
            attempts.append((dynamic_modes[0], None))
        else:
            for selector in prioritized_selectors:
                for mode in modes:
                    attempts.append((mode, selector))
            attempts.append((modes[0], None))

        deduped_attempts: list[tuple[str, str | None]] = []
        seen_attempts: set[tuple[str, str | None]] = set()
        for attempt in attempts:
            if attempt in seen_attempts:
                continue
            deduped_attempts.append(attempt)
            seen_attempts.add(attempt)
            if len(deduped_attempts) >= max_attempts:
                break

        for mode, selector in deduped_attempts:
            output_file = tmpdir / f"{platform_key}_{mode}.txt"
            args = [scrapling_bin, "extract", mode, url, str(output_file)]
            if mode == "get":
                args.append("--no-verify")
                cookie_header = resolve_cookie_header(url, request_options)
                if cookie_header:
                    args.extend(["--cookies", cookie_header])
                args.extend(build_scrapling_header_args(
                    url,
                    request_options,
                    "-H",
                    include_cookie=not bool(cookie_header),
                ))
            if mode in {"fetch", "stealthy-fetch"}:
                args.extend(["--timeout", "20000", "--wait", "1500"])
                args.extend(build_scrapling_header_args(url, request_options, "-H"))
            if mode == "stealthy-fetch":
                args.extend(["--network-idle", "--solve-cloudflare"])
            if selector:
                args.extend(["--css-selector", selector])
                if (
                    mode in {"fetch", "stealthy-fetch"}
                    and platform_key in SCRAPLING_DYNAMIC_PLATFORMS
                    and selector not in {"body", "main", "article"}
                ):
                    args.extend(["--wait-selector", selector])

            result = run_command(
                args,
                timeout=SCRAPLING_MODE_TIMEOUTS.get(mode, 45),
                env=scrapling_env,
            )
            if result.returncode == 0 and output_file.exists():
                text = normalize_space(output_file.read_text(encoding="utf-8", errors="replace"))
                if len(text) >= 120:
                    suffix = f" [{selector}]" if selector else ""
                    return text, f"scrapling {mode}{suffix}", warnings

            error = normalize_space(result.stderr or result.stdout)
            if result.returncode != 0 and error:
                if "No module named" in error or "browserforge" in error:
                    warnings.append(
                        "Scrapling 已存在但依赖不完整。运行 bash scripts/bootstrap.sh --install-python 完成本地运行时安装。"
                    )
                    return None, None, warnings
                warnings.append(shorten(f"Scrapling {mode} 失败: {error}", 220))

    return None, None, warnings


def extract_web_text(
    url: str,
    request_options: RequestOptions,
    html: str | None = None,
    platform_key: str = "web",
) -> tuple[str | None, str, list[str]]:
    warnings: list[str] = []
    if platform_key in SCRAPLING_DYNAMIC_PLATFORMS:
        scrapling_text, scrapling_method, scrapling_warnings = extract_with_scrapling(
            url,
            platform_key,
            request_options,
        )
        warnings.extend(scrapling_warnings)
        if scrapling_text:
            return scrapling_text[:12000], scrapling_method or "scrapling", warnings

    if not html and platform_key not in SCRAPLING_DYNAMIC_PLATFORMS:
        scrapling_text, scrapling_method, scrapling_warnings = extract_with_scrapling(
            url,
            platform_key,
            request_options,
        )
        warnings.extend(scrapling_warnings)
        if scrapling_text:
            return scrapling_text[:12000], scrapling_method or "scrapling", warnings

    if html is None:
        html, _, html_warnings = fetch_html(url, request_options)
        warnings.extend(html_warnings)

    if html:
        local_text, local_warnings = extract_with_trafilatura(html)
        warnings.extend(local_warnings)
        if local_text:
            return local_text[:12000], "trafilatura", warnings

    summarize_bin = find_summarize_bin()
    if summarize_bin:
        result = run_command(
            [summarize_bin, url, "--extract-only", "--max-output-tokens", "8000"],
            timeout=180,
        )
        if result.returncode == 0:
            text = normalize_space(result.stdout)
            if len(text) >= 120:
                return text, "summarize --extract-only", warnings
        else:
            error = normalize_space(result.stderr or result.stdout)
            warnings.append(f"summarize 提取失败: {shorten(error, 160)}")

    if html:
        text = html_to_text(html)
        if text:
            return text[:12000], "html fallback", warnings
    return None, "unavailable", warnings


def read_local_file(path: Path) -> tuple[str | None, str, list[str]]:
    warnings: list[str] = []
    ext = path.suffix.lower()

    if ext in {".txt", ".md", ".markdown", ".json", ".csv", ".log"}:
        return normalize_space(path.read_text(encoding="utf-8", errors="replace")), "local text file", warnings

    if ext == ".pdf":
        summarize_bin = find_summarize_bin()
        if not summarize_bin:
            return None, "unavailable", ["缺少 summarize，无法提取 PDF。"]
        result = run_command(
            [summarize_bin, str(path), "--extract-only", "--max-output-tokens", "8000"],
            timeout=180,
        )
        if result.returncode != 0:
            error = normalize_space(result.stderr or result.stdout)
            return None, "unavailable", [f"PDF 提取失败: {shorten(error, 160)}"]
        return normalize_space(result.stdout), "summarize pdf", warnings

    if ext in {".mp4", ".mov", ".avi", ".mkv", ".mp3", ".wav", ".m4a"}:
        with tempfile.TemporaryDirectory() as tmp:
            text, transcribe_warnings = transcribe_with_whisper(path, Path(tmp))
            warnings.extend(transcribe_warnings)
            if text:
                return text, "local whisper transcription", warnings
        return None, "unavailable", warnings

    return None, "unavailable", [f"暂不支持的本地文件类型: {ext or 'unknown'}"]


def tokenize(text: str) -> list[str]:
    analysis_text = limit_analysis_text(text)
    raw_tokens = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}|[\u4e00-\u9fff]{2,12}", analysis_text.lower())
    tokens = []
    for token in raw_tokens:
        if token in STOP_WORDS:
            continue
        if token.isdigit():
            continue
        tokens.append(token)
    return tokens


def split_sentences(text: str) -> list[str]:
    normalized = limit_analysis_text(text)
    parts = re.split(r"(?<=[。！？!?])\s*|(?<=\.)\s+|\n+", normalized)
    sentences = [part.strip() for part in parts if part and len(part.strip()) >= 12]
    return sentences[:ANALYSIS_SENTENCE_LIMIT]


def rank_sentences(text: str, max_sentences: int = 3) -> list[str]:
    sentences = split_sentences(text)
    if not sentences:
        return []

    frequency: dict[str, int] = {}
    for token in tokenize(text):
        frequency[token] = frequency.get(token, 0) + 1

    scored: list[tuple[float, int, str]] = []
    for index, sentence in enumerate(sentences):
        sentence_tokens = tokenize(sentence)
        if not sentence_tokens:
            continue
        score = sum(frequency.get(token, 0) for token in sentence_tokens) / len(sentence_tokens)
        if re.search(r"\d", sentence):
            score += 0.25
        scored.append((score, index, sentence))

    top = sorted(scored, key=lambda item: item[0], reverse=True)[:max_sentences]
    ordered = [sentence for _, _, sentence in sorted(top, key=lambda item: item[1])]
    unique: list[str] = []
    seen = set()
    for sentence in ordered:
        if sentence not in seen:
            unique.append(sentence)
            seen.add(sentence)
    return unique


def extract_keywords(text: str, limit: int = 6) -> list[str]:
    counts: dict[str, int] = {}
    for token in tokenize(text):
        counts[token] = counts.get(token, 0) + 1
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [token for token, _ in ranked[:limit]]


def derive_title_from_content(content: str, fallback: str) -> str:
    candidates = rank_sentences(content, max_sentences=1) or split_sentences(content)[:1]
    if not candidates:
        return fallback
    candidate = candidates[0].strip().strip("“”\"'：:[]【】")
    candidate = re.sub(r"^(原标题[:：])", "", candidate).strip()
    return shorten(candidate or fallback, 64)


def build_local_item_analysis(item: dict[str, object]) -> str:
    platform = str(item.get("platform") or "内容")
    summary = str(item.get("summary") or "").strip()
    highlights = [str(value) for value in list(item.get("highlights") or []) if str(value).strip()]
    keywords = [str(value) for value in list(item.get("keywords") or []) if str(value).strip()]
    source_metadata = item.get("source_metadata")
    metadata = source_metadata if isinstance(source_metadata, dict) else {}

    if str(item.get("platform_key") or "") == "github":
        topics = ", ".join(str(value) for value in list(metadata.get("topics") or [])[:4])
        stars = metadata.get("stargazers_count") or 0
        language = str(metadata.get("language") or "未识别")
        description = str(metadata.get("description") or summary or "仓库 README 已提取，可继续分析安装方式与核心模块。")
        focus = "建议优先看 README 的安装步骤、目录结构和最近更新点。"
        if topics:
            focus = f"建议优先看 {topics} 相关模块，以及 README 的安装步骤和示例。"
        return "\n".join([
            f"核心价值：{shorten(description, 120)}",
            f"适用场景：这是一个 {language} 项目，当前约 {stars} stars，适合做仓库筛选、README 解读和方案评估。",
            f"关注点：{focus}",
        ])

    lead = highlights[0] if highlights else summary or f"{platform} 内容已完成抽取。"
    scene = f"适用场景：适合快速了解这条{platform}内容的重点，再决定是否继续深入阅读原文。"
    if keywords:
        scene = f"适用场景：适合围绕 {', '.join(keywords[:4])} 这些关键词继续做延伸分析或归档。"
    concern = "关注点：建议结合原文摘录核对关键结论，避免只看摘要做判断。"
    return "\n".join([
        f"核心价值：{shorten(lead, 120)}",
        scene,
        concern,
    ])


def extract_response_text(payload: object) -> str:
    chunks: list[str] = []

    def visit(value: object) -> None:
        if isinstance(value, dict):
            value_type = str(value.get("type") or "")
            text_value = value.get("text")
            if value_type in {"output_text", "text"} and isinstance(text_value, str):
                chunks.append(text_value)
            for child in value.values():
                visit(child)
            return
        if isinstance(value, list):
            for child in value:
                visit(child)

    visit(payload)
    return normalize_space("\n".join(chunks))


def resolve_openai_responses_url() -> str:
    explicit = os.environ.get("CONTENT_PROCESSOR_OPENAI_RESPONSES_URL")
    if explicit:
        return explicit
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com").rstrip("/")
    if base_url.endswith("/v1"):
        return f"{base_url}/responses"
    return f"{base_url}/v1/responses"


def request_llm_analysis(prompt: str, analysis_options: AnalysisOptions) -> tuple[str | None, str | None]:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None, None

    request_body = {
        "model": analysis_options.model,
        "input": prompt,
        "max_output_tokens": 400,
    }
    request_data = json.dumps(request_body).encode("utf-8")
    request = Request(
        resolve_openai_responses_url(),
        data=request_data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=analysis_options.timeout) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except Exception:  # noqa: BLE001
        return None, None

    text = extract_response_text(payload)
    if not text:
        return None, None
    return text, f"openai responses ({analysis_options.model})"


def build_item_analysis_prompt(item: dict[str, object]) -> str:
    metadata = item.get("source_metadata")
    metadata_block = json.dumps(metadata, ensure_ascii=False, indent=2) if isinstance(metadata, dict) and metadata else "{}"
    content = shorten(str(item.get("content") or ""), 5000)
    highlights = "\n".join(f"- {value}" for value in list(item.get("highlights") or [])[:3])
    return "\n".join([
        "你是一个内容分析助手。请用中文输出三行，每行都以固定标签开头：",
        "核心价值：...",
        "适用场景：...",
        "关注点：...",
        "",
        f"平台：{item.get('platform') or ''}",
        f"标题：{item.get('title') or ''}",
        f"作者：{item.get('author') or ''}",
        f"摘要：{item.get('summary') or ''}",
        f"核心信息：\n{highlights}",
        f"来源元数据：\n{metadata_block}",
        f"正文片段：\n{content}",
    ])


def enrich_item_analysis(item: dict[str, object], analysis_options: AnalysisOptions) -> dict[str, object]:
    if analysis_options.mode == "off":
        item["analysis"] = ""
        item["analysis_method"] = "disabled"
        return item

    if analysis_options.mode in {"auto", "llm"}:
        prompt = build_item_analysis_prompt(item)
        analysis_text, analysis_method = request_llm_analysis(prompt, analysis_options)
        if analysis_text and analysis_method:
            item["analysis"] = analysis_text
            item["analysis_method"] = analysis_method
            return item

    item["analysis"] = build_local_item_analysis(item)
    item["analysis_method"] = "local heuristic"
    return item


def build_local_report_analysis(items: list[dict[str, object]]) -> str:
    successful = [item for item in items if str(item.get("status") or "") == "success"]
    if not successful:
        return "这一批链接已经完成抓取，但成功提取正文的来源较少，建议优先查看各来源告警后再做后续动作。"

    top_titles = [str(item.get("title") or "") for item in successful[:3] if str(item.get("title") or "").strip()]
    keywords = []
    for item in successful:
        keywords.extend(list(item.get("keywords") or [])[:2])
    unique_keywords = []
    for value in keywords:
        text = str(value).strip()
        if text and text not in unique_keywords:
            unique_keywords.append(text)
    lead = f"这一批内容里，优先值得看的来源有：{'、'.join(top_titles)}。" if top_titles else "这一批内容已经完成抽取。"
    follow_up = "后续建议优先围绕 " + "、".join(unique_keywords[:5]) + " 继续做延伸归档或深度分析。" if unique_keywords else "后续建议根据各条摘要和原文摘录决定是否继续深挖。"
    return f"{lead} {follow_up}"


def build_report_analysis_prompt(items: list[dict[str, object]]) -> str:
    item_blocks = []
    for item in items[:8]:
        item_blocks.append(
            "\n".join([
                f"标题：{item.get('title') or ''}",
                f"平台：{item.get('platform') or ''}",
                f"摘要：{item.get('summary') or ''}",
                f"分析：{item.get('analysis') or ''}",
            ])
        )
    return "\n".join([
        "你是一个信息汇总分析助手。请用中文输出一个短段落，回答：这批内容最值得关注的共同主题是什么，下一步应该看什么。",
        "",
        "\n\n".join(item_blocks),
    ])


def build_report_analysis(
    items: list[dict[str, object]],
    analysis_options: AnalysisOptions,
) -> tuple[str, str]:
    if analysis_options.mode in {"auto", "llm"}:
        analysis_text, analysis_method = request_llm_analysis(
            build_report_analysis_prompt(items),
            analysis_options,
        )
        if analysis_text and analysis_method:
            return analysis_text, analysis_method
    return build_local_report_analysis(items), "local heuristic"


def build_item(
    source: str,
    max_content_chars: int,
    request_options: RequestOptions,
) -> dict[str, object]:
    platform_key, detail = classify_source(source)
    label = PLATFORM_LABELS.get(platform_key, platform_key)
    item: dict[str, object] = {
        "source": source,
        "platform_key": platform_key,
        "platform": label,
        "detail": detail,
        "title": "",
        "author": "",
        "published_at": "",
        "duration": "",
        "extract_method": "",
        "summary": "",
        "highlights": [],
        "keywords": [],
        "content": "",
        "warnings": [],
        "status": "pending",
        "warning_count": 0,
        "content_chars": 0,
        "failure_code": "",
        "analysis": "",
        "analysis_method": "",
        "source_metadata": {},
    }

    if platform_key == "file":
        path = Path(source).expanduser()
        content, method, warnings = read_local_file(path)
        item["title"] = path.stem
        item["author"] = "本地文件"
        item["extract_method"] = method
        item["warnings"] = warnings
        if content:
            item["content"] = content[:max_content_chars]
        return finalize_item(item)

    metadata: dict[str, object] = {}
    content: str | None = None
    warnings: list[str] = []
    html: str | None = None
    html_metadata: dict[str, str] = {}
    used_host_title_fallback = False

    if platform_key == "github":
        source_metadata, github_content, github_method, github_warnings = extract_github_repo(source, request_options)
        warnings.extend(github_warnings)
        if source_metadata:
            item["source_metadata"] = source_metadata
            item["title"] = str(
                source_metadata.get("full_name")
                or item.get("title")
                or ""
            )
            item["author"] = str(source_metadata.get("full_name") or "").split("/")[0]
            item["published_at"] = str(source_metadata.get("updated_at") or "")
        if github_content:
            content = github_content
            item["extract_method"] = github_method or "github api"

    if platform_key in {"youtube", "bilibili", "douyin", "xiaohongshu", "weibo", "x"}:
        metadata, meta_warnings = load_yt_metadata(source, request_options)
        warnings.extend(meta_warnings)
        item["title"] = str(metadata.get("title") or "")
        item["author"] = str(
            metadata.get("uploader")
            or metadata.get("channel")
            or metadata.get("creator")
            or metadata.get("uploader_id")
            or ""
        )
        upload_date = str(metadata.get("upload_date") or "")
        if len(upload_date) == 8 and upload_date.isdigit():
            item["published_at"] = (
                f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]}"
            )
        else:
            item["published_at"] = str(metadata.get("release_timestamp") or "")
        duration = metadata.get("duration")
        if isinstance(duration, (int, float)):
            item["duration"] = format_duration(duration) or ""
        elif metadata.get("duration_string"):
            item["duration"] = str(metadata["duration_string"])

        description = clean_transcript_text(str(metadata.get("description") or ""))
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            subtitle_text, subtitle_method, subtitle_warnings = fetch_yt_subtitles(
                source,
                tmpdir,
                request_options,
            )
            warnings.extend(subtitle_warnings)
            if subtitle_text:
                content = normalize_space("\n\n".join(part for part in [description, subtitle_text] if part))
                item["extract_method"] = subtitle_method or "yt-dlp subtitles"
            else:
                downloaded, download_warnings = download_media_for_transcription(
                    source,
                    tmpdir,
                    request_options,
                )
                warnings.extend(download_warnings)
                if downloaded:
                    transcript, transcribe_warnings = transcribe_with_whisper(downloaded, tmpdir)
                    warnings.extend(transcribe_warnings)
                    if transcript:
                        content = normalize_space("\n\n".join(part for part in [description, transcript] if part))
                        item["extract_method"] = "yt-dlp download + whisper-cli"

        if not content and description:
            content = description
            item["extract_method"] = item["extract_method"] or "yt-dlp metadata only"

    if not content:
        web_text, method, web_warnings = extract_web_text(
            source,
            request_options,
            html=None,
            platform_key=platform_key,
        )
        warnings.extend(web_warnings)
        if web_text:
            content = web_text
            item["extract_method"] = item["extract_method"] or method

        if not item["title"] or not item["author"] or not item["published_at"] or not content:
            html, html_metadata, html_warnings = fetch_html(source, request_options)
            if html:
                if not item["title"]:
                    item["title"] = html_metadata.get("title", "")
                if not item["author"]:
                    item["author"] = html_metadata.get("author") or html_metadata.get("site_name", "")
                if not item["published_at"]:
                    item["published_at"] = html_metadata.get("published_at", "")
                if not content:
                    fallback_text, fallback_method, fallback_warnings = extract_web_text(
                        source,
                        request_options,
                        html=html,
                        platform_key=platform_key,
                    )
                    warnings.extend(fallback_warnings)
                    if fallback_text:
                        content = fallback_text
                        item["extract_method"] = item["extract_method"] or fallback_method
            elif not content:
                warnings.extend(html_warnings)

    if not item["title"]:
        parsed = urlparse(source)
        fallback_title = parsed.netloc or source
        item["title"] = fallback_title
        used_host_title_fallback = True

    if content and used_host_title_fallback:
        item["title"] = derive_title_from_content(content, str(item["title"]))

    item["warnings"] = warnings
    if content:
        item["content"] = content[:max_content_chars]
    return finalize_item(item)


def finalize_item(item: dict[str, object]) -> dict[str, object]:
    content = str(item.get("content") or "")
    warnings = list(item.get("warnings") or [])
    if content:
        highlights = rank_sentences(content, max_sentences=3)
        summary = " ".join(highlights) or shorten(content, 220)
        item["summary"] = shorten(summary, 420)
        item["highlights"] = [shorten(line, 180) for line in highlights[:3]]
        item["keywords"] = extract_keywords(content, limit=6)
    else:
        item["summary"] = "未能提取到足够正文，只保留了来源元数据。"
        item["highlights"] = []
        item["keywords"] = []
        warnings.append("正文为空或过短。")
        item["warnings"] = warnings
        item["failure_code"] = str(item.get("failure_code") or derive_failure_code(warnings))
    item["content_chars"] = len(content)
    item["warning_count"] = len(warnings)
    item["status"] = summarize_item_status(item)
    if item["status"] != "failed":
        item["failure_code"] = ""
    return item


def render_quote_block(text: str, limit: int = 400) -> str:
    snippet = shorten(text.replace("\n", " "), limit)
    wrapped = textwrap.wrap(snippet, width=78) or [snippet]
    return "\n".join(f"> {line}" for line in wrapped)


def render_report(
    title: str,
    items: list[dict[str, object]],
    output_dir: Path,
    report_analysis: str,
    report_analysis_method: str,
) -> str:
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    run_summary = build_run_summary(items)
    all_text = "\n\n".join(str(item.get("summary") or "") for item in items)
    overall = " ".join(rank_sentences(all_text, max_sentences=4))
    if not overall:
        overall = "已完成链接抓取，但部分来源只拿到了元数据，建议查看各来源告警。"
    overview_keywords = extract_keywords(all_text, limit=8)

    lines = [
        f"# {title}",
        "",
        f"- 生成时间：{generated_at}",
        f"- 处理状态：{run_summary['status']}",
        f"- 链接数量：{run_summary['item_count']}",
        f"- 成功：{run_summary['success_count']}",
        f"- 部分成功：{run_summary['partial_count']}",
        f"- 失败：{run_summary['failed_count']}",
        f"- 输出目录：{output_dir}",
    ]
    if overview_keywords:
        lines.append(f"- 主题关键词：{', '.join(overview_keywords)}")

    lines.extend(
        [
            "",
            "## 总览",
            "",
            report_analysis or overall,
            "",
            "## 来源清单",
            "",
        ]
    )
    lines.append(f"- 总览分析方式：{report_analysis_method}")

    for index, item in enumerate(items, start=1):
        title_text = str(item.get("title") or "未命名")
        platform = str(item.get("platform") or "未知平台")
        author = str(item.get("author") or "未知来源")
        lines.append(f"{index}. [{platform}] {title_text} - {author}")

    for index, item in enumerate(items, start=1):
        title_text = str(item.get("title") or "未命名")
        lines.extend(
            [
                "",
                f"## {index}. {title_text}",
                "",
                f"- 状态：{item.get('status') or 'unknown'}",
                f"- 平台：{item.get('platform') or '未知平台'}",
                f"- 原始链接：{item.get('source') or '-'}",
                f"- 作者/来源：{item.get('author') or '-'}",
            ]
        )
        if item.get("published_at"):
            lines.append(f"- 发布时间：{item['published_at']}")
        if item.get("duration"):
            lines.append(f"- 时长：{item['duration']}")
        if item.get("extract_method"):
            lines.append(f"- 抽取方式：{item['extract_method']}")
        if item.get("keywords"):
            lines.append(f"- 关键词：{', '.join(item['keywords'])}")
        if item.get("warnings"):
            lines.append(f"- 告警：{' | '.join(item['warnings'])}")

        lines.extend(
            [
                "",
                "### 摘要",
                "",
                str(item.get("summary") or ""),
            ]
        )

        if item.get("analysis"):
            lines.extend(
                [
                    "",
                    "### 分析",
                    "",
                    str(item.get("analysis") or ""),
                    "",
                    f"- 分析方式：{item.get('analysis_method') or '-'}",
                ]
            )

        highlights = list(item.get("highlights") or [])
        if highlights:
            lines.extend(["", "### 核心信息", ""])
            for highlight in highlights:
                lines.append(f"- {highlight}")

        content = str(item.get("content") or "")
        if content:
            lines.extend(
                [
                    "",
                    "### 原文摘录",
                    "",
                    render_quote_block(content),
                ]
            )

    return "\n".join(lines).strip() + "\n"


def write_item_files(items: list[dict[str, object]], item_dir: Path) -> None:
    item_dir.mkdir(parents=True, exist_ok=True)
    for index, item in enumerate(items, start=1):
        filename = f"{index:02d}_{sanitize_filename(str(item.get('title') or item.get('platform') or 'item'))}.json"
        (item_dir / filename).write_text(
            json.dumps(item, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def derive_report_title(cli_title: str | None, items: list[dict[str, object]]) -> str:
    if cli_title:
        return cli_title
    if len(items) == 1:
        base = str(items[0].get("title") or "内容摘要")
        return f"{shorten(base, 32)} 内容摘要"
    return "多平台信息汇总"


def build_output_dir(output_root: Path, report_title: str) -> Path:
    date_dir = output_root / datetime.now().strftime("%Y-%m-%d")
    slug = sanitize_filename(report_title, default="content-report")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = date_dir / f"{timestamp}_{slug}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def build_request_options(args: argparse.Namespace) -> RequestOptions:
    extra_headers = parse_header_values(args.header or [])
    if args.referer:
        extra_headers.setdefault("Referer", args.referer)
    return RequestOptions(
        cookie_header=normalize_cookie_header(args.cookie_header),
        cookies_file=args.cookies_file or "",
        cookies_from_browser=args.cookies_from_browser or "",
        extra_headers=extra_headers,
    )


def build_analysis_options(args: argparse.Namespace) -> AnalysisOptions:
    return AnalysisOptions(
        mode=args.analysis_mode,
        model=args.analysis_model or DEFAULT_ANALYSIS_MODEL,
        timeout=args.analysis_timeout,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Process one or more share links and save a desktop report."
    )
    parser.add_argument("sources", nargs="+", help="URLs, local files, or pasted share text.")
    parser.add_argument("--report-title", help="Custom report title.")
    parser.add_argument(
        "--output-root",
        default=str(DEFAULT_OUTPUT_ROOT),
        help=f"Desktop output root. Default: {DEFAULT_OUTPUT_ROOT}",
    )
    parser.add_argument(
        "--max-content-chars",
        type=int,
        default=30000,
        help="Maximum raw content chars stored per item.",
    )
    parser.add_argument(
        "--cookies-file",
        default=os.environ.get("CONTENT_PROCESSOR_COOKIES_FILE", ""),
        help="Netscape cookie file for protected pages. Can also be set via CONTENT_PROCESSOR_COOKIES_FILE.",
    )
    parser.add_argument(
        "--cookies-from-browser",
        default=os.environ.get("CONTENT_PROCESSOR_COOKIES_FROM_BROWSER", ""),
        help="Browser session for yt-dlp, e.g. chrome, safari, firefox. Can also be set via CONTENT_PROCESSOR_COOKIES_FROM_BROWSER.",
    )
    parser.add_argument(
        "--cookie-header",
        default=os.environ.get("CONTENT_PROCESSOR_COOKIE_HEADER", ""),
        help="Raw Cookie header for static/scrapling requests. Can also be set via CONTENT_PROCESSOR_COOKIE_HEADER.",
    )
    parser.add_argument(
        "--header",
        action="append",
        default=[],
        help='Extra HTTP header in "Key: Value" format. Repeatable.',
    )
    parser.add_argument(
        "--referer",
        default=os.environ.get("CONTENT_PROCESSOR_REFERER", ""),
        help="Optional Referer header. Can also be set via CONTENT_PROCESSOR_REFERER.",
    )
    parser.add_argument(
        "--analysis-mode",
        choices=["auto", "off", "heuristic", "llm"],
        default=os.environ.get("CONTENT_PROCESSOR_ANALYSIS_MODE", "auto"),
        help="How to build item/report analysis. auto tries OpenAI API then falls back to local heuristic.",
    )
    parser.add_argument(
        "--analysis-model",
        default=os.environ.get("CONTENT_PROCESSOR_ANALYSIS_MODEL", DEFAULT_ANALYSIS_MODEL),
        help="OpenAI model for analysis mode llm/auto.",
    )
    parser.add_argument(
        "--analysis-timeout",
        type=int,
        default=int(os.environ.get("CONTENT_PROCESSOR_ANALYSIS_TIMEOUT", "60")),
        help="Timeout in seconds for the optional LLM analysis step.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        request_options = build_request_options(args)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    analysis_options = build_analysis_options(args)

    sources = extract_sources(args.sources)
    if not sources:
        print("No valid sources found.", file=sys.stderr)
        return 1

    items: list[dict[str, object]] = []
    for index, source in enumerate(sources, start=1):
        log(f"Processing: {source}")
        item = build_item(
            source,
            max_content_chars=args.max_content_chars,
            request_options=request_options,
        )
        item["source_id"] = f"item-{index:02d}"
        items.append(enrich_item_analysis(item, analysis_options))

    report_title = derive_report_title(args.report_title, items)
    output_root = Path(args.output_root).expanduser()
    run_dir = build_output_dir(output_root, report_title)

    report_md = run_dir / "report.md"
    report_json = run_dir / "report.json"
    item_dir = run_dir / "items"

    write_item_files(items, item_dir)
    report_analysis, report_analysis_method = build_report_analysis(items, analysis_options)
    report_md.write_text(
        render_report(report_title, items, run_dir, report_analysis, report_analysis_method),
        encoding="utf-8",
    )
    run_summary = build_run_summary(items)

    payload = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": run_summary["status"],
        "report_title": report_title,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "output_dir": str(run_dir),
        "report_md": str(report_md),
        "report_json": str(report_json),
        "request_options": {
            "cookies_file": request_options.cookies_file,
            "cookies_from_browser": request_options.cookies_from_browser,
            "cookie_header_configured": bool(request_options.cookie_header),
            "extra_headers": sorted(request_options.extra_headers.keys()),
        },
        "analysis_options": {
            "mode": analysis_options.mode,
            "model": analysis_options.model,
            "timeout": analysis_options.timeout,
        },
        "summary": run_summary,
        "overview_analysis": report_analysis,
        "overview_analysis_method": report_analysis_method,
        "tool_info": build_tool_info(),
        "sources": sources,
        "items": items,
    }
    report_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(
        {
            "schema_version": REPORT_SCHEMA_VERSION,
            "status": run_summary["status"],
            "report_title": report_title,
            "output_dir": str(run_dir),
            "report_md": str(report_md),
            "report_json": str(report_json),
            "item_count": run_summary["item_count"],
            "success_count": run_summary["success_count"],
            "partial_count": run_summary["partial_count"],
            "failed_count": run_summary["failed_count"],
        },
        ensure_ascii=False,
        indent=2,
    ))
    return {"success": 0, "partial": 2, "failed": 3}[str(run_summary["status"])]


if __name__ == "__main__":
    raise SystemExit(main())
