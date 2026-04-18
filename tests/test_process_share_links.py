import importlib.util
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "process_share_links.py"
SPEC = importlib.util.spec_from_file_location("content_processor", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ContentProcessorTests(unittest.TestCase):
    def test_extract_sources_dedupes_and_preserves_order(self) -> None:
        sources = MODULE.extract_sources([
            "看这个 https://example.com/a",
            "https://example.com/a",
            "https://example.com/b",
        ])
        self.assertEqual(sources, ["https://example.com/a", "https://example.com/b"])

    def test_extract_source_inputs_preserves_share_context_for_urls(self) -> None:
        sources = MODULE.extract_source_inputs([
            "8.23 复制打开抖音，看看【疯码牛的作品】第一个出厂就带缰绳的AI Agent https://v.douyin.com/demo/ y@G.VL 07/16 uSY:/ ，摘要这个",
        ])
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0].source, "https://v.douyin.com/demo/")
        self.assertEqual(sources[0].context_text, "【疯码牛的作品】第一个出厂就带缰绳的AI Agent")

    def test_serialize_source_inputs_returns_json_ready_payload(self) -> None:
        payload = MODULE.serialize_source_inputs([
            MODULE.SourceInput("https://v.douyin.com/demo/", "【疯码牛的作品】第一个出厂就带缰绳的AI Agent"),
        ])
        self.assertEqual(payload, [
            {
                "source": "https://v.douyin.com/demo/",
                "context_text": "【疯码牛的作品】第一个出厂就带缰绳的AI Agent",
            }
        ])

    def test_maybe_attach_saved_douyin_auth_uses_saved_cookie_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cookie_file = Path(tmp) / "cookies.txt"
            cookie_file.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
            request_options = MODULE.RequestOptions()
            with mock.patch.object(MODULE, "DOUYIN_AUTH_COOKIES_FILE", cookie_file):
                updated = MODULE.maybe_attach_saved_douyin_auth(
                    [MODULE.SourceInput("https://v.douyin.com/demo/")],
                    request_options,
                )
        self.assertEqual(updated.cookies_file, str(cookie_file))

    def test_download_douyin_media_with_playwright_parses_json_payload(self) -> None:
        payload = {
            "status": "success",
            "primary_media_url": "https://example.com/video.mp4",
            "downloaded_file": "/tmp/video.mp4",
            "warnings": [],
        }
        completed = MODULE.subprocess.CompletedProcess(
            args=["python3"],
            returncode=0,
            stdout=MODULE.json.dumps(payload, ensure_ascii=False),
            stderr="",
        )
        with tempfile.TemporaryDirectory() as tmp:
            helper_script = Path(tmp) / "douyin_auth.py"
            helper_script.write_text("# helper\n", encoding="utf-8")
            with (
                mock.patch.object(MODULE, "DOUYIN_AUTH_SCRIPT", helper_script),
                mock.patch.object(MODULE, "run_command", return_value=completed),
            ):
                result, warnings = MODULE.download_douyin_media_with_playwright(
                    "https://v.douyin.com/demo/",
                    Path("/tmp"),
                )
        self.assertEqual(result["primary_media_url"], "https://example.com/video.mp4")
        self.assertEqual(warnings, [])

    def test_maybe_run_douyin_login_updates_request_options_on_success(self) -> None:
        payload = {"status": "success", "cookies_txt": "/tmp/cookies.txt"}
        completed = MODULE.subprocess.CompletedProcess(
            args=["python3"],
            returncode=0,
            stdout=MODULE.json.dumps(payload, ensure_ascii=False),
            stderr="",
        )
        request_options = MODULE.RequestOptions(auto_login_douyin=True)
        with tempfile.TemporaryDirectory() as tmp:
            helper_script = Path(tmp) / "douyin_auth.py"
            helper_script.write_text("# helper\n", encoding="utf-8")
            cookie_file = Path(tmp) / "cookies.txt"
            cookie_file.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
            with (
                mock.patch.object(MODULE, "DOUYIN_AUTH_SCRIPT", helper_script),
                mock.patch.object(MODULE, "DOUYIN_AUTH_COOKIES_FILE", cookie_file),
                mock.patch.object(MODULE, "run_command", return_value=completed),
                mock.patch.object(MODULE.sys.stdin, "isatty", return_value=True),
                mock.patch.object(MODULE.sys.stdout, "isatty", return_value=True),
            ):
                login_payload, warnings = MODULE.maybe_run_douyin_login(request_options)

        self.assertEqual(login_payload["status"], "success")
        self.assertEqual(warnings, [])
        self.assertEqual(request_options.cookies_file, str(cookie_file))
        self.assertEqual(request_options.cookies_from_browser, "")
        self.assertEqual(request_options.cookie_header, "")
        self.assertTrue(request_options.douyin_login_attempted)

    def test_cleanup_transient_media_file_removes_only_tmpdir_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            inside = tmpdir / "inside.mp4"
            inside.write_bytes(b"video")
            MODULE.cleanup_transient_media_file(inside, tmpdir)
            self.assertFalse(inside.exists())

        with tempfile.TemporaryDirectory() as tmp:
            outside_parent = Path(tmp)
            outside = outside_parent / "outside.mp4"
            outside.write_bytes(b"video")
            with tempfile.TemporaryDirectory() as other:
                MODULE.cleanup_transient_media_file(outside, Path(other))
            self.assertTrue(outside.exists())

    def test_classify_source_detects_github_repo(self) -> None:
        self.assertEqual(
            MODULE.classify_source("https://github.com/shadcn-ui/ui"),
            ("github", "repo"),
        )

    def test_parse_header_values_rejects_invalid_format(self) -> None:
        with self.assertRaises(ValueError):
            MODULE.parse_header_values(["invalid-header"])

    def test_parse_github_source_handles_blob_url(self) -> None:
        parsed = MODULE.parse_github_source("https://github.com/openai/openai-python/blob/main/README.md")
        self.assertEqual(parsed["owner"], "openai")
        self.assertEqual(parsed["repo"], "openai-python")
        self.assertEqual(parsed["kind"], "blob")
        self.assertEqual(parsed["path"], "README.md")

    def test_resolve_cookie_header_from_netscape_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cookie_file = Path(tmp) / "cookies.txt"
            cookie_file.write_text(
                "# Netscape HTTP Cookie File\n"
                ".example.com\tTRUE\t/\tFALSE\t2147483647\tsessionid\tabc123\n",
                encoding="utf-8",
            )
            request_options = MODULE.RequestOptions(cookies_file=str(cookie_file))
            headers = MODULE.build_request_headers("https://example.com/article", request_options)

        self.assertEqual(headers["User-Agent"], MODULE.USER_AGENT)
        self.assertEqual(headers["Cookie"], "sessionid=abc123")

    def test_finalize_item_marks_partial_when_content_has_warnings(self) -> None:
        item = MODULE.finalize_item({
            "content": "这是一个足够长的测试句子，用来模拟已经提取到正文。" * 3,
            "warnings": ["summarize 提取失败，已回退"],
        })
        self.assertEqual(item["status"], "partial")
        self.assertEqual(item["warning_count"], 1)
        self.assertGreater(int(item["content_chars"]), 0)

    def test_finalize_item_marks_failed_when_content_missing(self) -> None:
        item = MODULE.finalize_item({
            "content": "",
            "warnings": ["缺少 summarize"],
        })
        self.assertEqual(item["status"], "failed")
        self.assertEqual(item["failure_code"], "missing_dependency")

    def test_finalize_item_marks_auth_required_when_cookies_missing(self) -> None:
        item = MODULE.finalize_item({
            "content": "",
            "warnings": ["ERROR: [Douyin] Fresh cookies are needed"],
        })
        self.assertEqual(item["status"], "failed")
        self.assertEqual(item["failure_code"], "auth_required")

    def test_build_run_summary_counts_statuses(self) -> None:
        summary = MODULE.build_run_summary([
            {"status": "success", "warning_count": 0},
            {"status": "partial", "warning_count": 2},
            {"status": "failed", "warning_count": 1},
        ])
        self.assertEqual(summary["status"], "partial")
        self.assertEqual(summary["success_count"], 1)
        self.assertEqual(summary["partial_count"], 1)
        self.assertEqual(summary["failed_count"], 1)
        self.assertEqual(summary["warning_count"], 3)

    def test_run_command_timeout_returns_completed_process(self) -> None:
        result = MODULE.run_command(
            [sys.executable, "-c", "import time; time.sleep(0.2)"],
            timeout=0.05,
        )
        self.assertEqual(result.returncode, 124)
        self.assertIn("timed out", (result.stderr or "").lower())

    def test_derive_title_from_content_prefers_first_highlight(self) -> None:
        title = MODULE.derive_title_from_content(
            "原标题：这是一个很清晰的标题。\n这里是正文第二句。",
            "www.example.com",
        )
        self.assertEqual(title, "这是一个很清晰的标题。")

    def test_split_sentences_limits_analysis_budget(self) -> None:
        text = "\n".join(f"这是第{i}段用于测试分析预算的长句子，应该被正常切分。" for i in range(260))
        sentences = MODULE.split_sentences(text)
        self.assertEqual(len(sentences), MODULE.ANALYSIS_SENTENCE_LIMIT)
        self.assertTrue(all(len(sentence) >= 12 for sentence in sentences))

    def test_clean_transcript_text_removes_music_cues_and_urls(self) -> None:
        text = "Have you seen this? https://t.co/abc123 (upbeat music) [Music]"
        cleaned = MODULE.clean_transcript_text(text)
        self.assertEqual(cleaned, "Have you seen this?")

    def test_build_local_item_analysis_for_github(self) -> None:
        text = MODULE.build_local_item_analysis({
            "platform": "GitHub",
            "platform_key": "github",
            "summary": "一个用于构建 UI 组件的仓库。",
            "source_metadata": {
                "description": "A component system.",
                "language": "TypeScript",
                "stargazers_count": 1000,
                "topics": ["ui", "components"],
            },
        })
        self.assertIn("核心价值：", text)
        self.assertIn("TypeScript", text)
        self.assertIn("1000", text)

    def test_enrich_item_analysis_falls_back_to_local_when_llm_missing(self) -> None:
        item = {
            "platform": "网页",
            "platform_key": "web",
            "summary": "这是一段测试摘要。",
            "highlights": ["重点一。"],
            "keywords": ["测试"],
            "content": "这里是正文。",
            "source_metadata": {},
        }
        with mock.patch.dict("os.environ", {"OPENAI_API_KEY": ""}, clear=False):
            enriched = MODULE.enrich_item_analysis(item, MODULE.AnalysisOptions(mode="auto", model="gpt-5-mini", timeout=5))
        self.assertEqual(enriched["analysis_method"], "local heuristic")
        self.assertIn("核心价值：", enriched["analysis"])

    def test_build_item_uses_share_text_fallback_when_media_extract_fails(self) -> None:
        with (
            mock.patch.object(MODULE, "load_yt_metadata", return_value=({}, ["Fresh cookies required"])),
            mock.patch.object(MODULE, "fetch_yt_subtitles", return_value=("", "", ["字幕抓取失败"])),
            mock.patch.object(MODULE, "download_media_for_transcription", return_value=(None, ["媒体下载失败"])),
            mock.patch.object(MODULE, "extract_web_text", return_value=("", "", ["网页正文提取失败"])),
            mock.patch.object(MODULE, "fetch_html", return_value=(None, {}, ["网页抓取失败"])),
        ):
            item = MODULE.build_item(
                "https://v.douyin.com/demo/",
                max_content_chars=1000,
                request_options=MODULE.RequestOptions(),
                source_context="复制打开抖音，看看【疯码牛的作品】第一个出厂就带缰绳的AI Agent，AI Age... y@G.VL 07/16 uSY:/ ，摘要这个",
            )

        self.assertEqual(item["status"], "failed")
        self.assertEqual(item["failure_code"], "auth_required")
        self.assertEqual(item["extract_method"], "share text fallback")
        self.assertEqual(item["author"], "疯码牛")
        self.assertIn("第一个出厂就带缰绳的AI Agent", item["title"])
        self.assertIn("分享文案摘要", " ".join(item["warnings"]))
        self.assertIn("带缰绳", item["summary"])

    def test_build_item_marks_success_when_douyin_playwright_fallback_transcribes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            downloaded = Path(tmp) / "douyin.mp4"
            downloaded.write_bytes(b"video")
            with (
                mock.patch.object(MODULE, "load_yt_metadata", return_value=({}, ["Fresh cookies required"])),
                mock.patch.object(MODULE, "fetch_yt_subtitles", return_value=("", "", ["字幕抓取失败"])),
                mock.patch.object(MODULE, "download_media_for_transcription", return_value=(None, ["媒体下载失败"])),
                mock.patch.object(
                    MODULE,
                    "download_douyin_media_with_playwright",
                    return_value=(
                        {
                            "status": "success",
                            "title": "测试抖音",
                            "author": "疯码牛",
                            "canonical_url": "https://www.douyin.com/video/demo",
                            "primary_media_url": "https://media.example.com/demo.mp4",
                            "downloaded_file": str(downloaded),
                            "source": "playwright-network",
                        },
                        [],
                    ),
                ),
                mock.patch.object(MODULE, "transcribe_with_whisper", return_value=("这是转写正文。" * 30, [])),
            ):
                item = MODULE.build_item(
                    "https://v.douyin.com/demo/",
                    max_content_chars=2000,
                    request_options=MODULE.RequestOptions(),
                )

        self.assertEqual(item["status"], "success")
        self.assertEqual(item["warning_count"], 0)
        self.assertEqual(item["extract_method"], "playwright douyin download + whisper-cli")
        self.assertEqual(item["title"], "测试抖音")
        self.assertEqual(item["author"], "疯码牛")
        self.assertEqual(item["source_metadata"]["canonical_url"], "https://www.douyin.com/video/demo")
        self.assertEqual(item["source_metadata"]["resolved_media_source"], "playwright-network")
        self.assertIn("这是转写正文", item["content"])

    def test_build_item_retries_douyin_login_before_playwright_fallback(self) -> None:
        with (
            mock.patch.object(
                MODULE,
                "load_yt_metadata",
                side_effect=[
                    ({}, ["Fresh cookies required"]),
                    ({"title": "登录后标题", "uploader": "疯码牛"}, []),
                ],
            ),
            mock.patch.object(
                MODULE,
                "fetch_yt_subtitles",
                side_effect=[
                    ("", "", ["字幕抓取失败"]),
                    ("登录后拿到的字幕正文。" * 20, "yt-dlp subtitles (retry.vtt)", []),
                ],
            ),
            mock.patch.object(
                MODULE,
                "download_media_for_transcription",
                return_value=(None, ["媒体下载失败"]),
            ),
            mock.patch.object(MODULE, "can_attempt_douyin_login", return_value=True),
            mock.patch.object(MODULE, "maybe_run_douyin_login", return_value=({"status": "success"}, [])) as login_mock,
            mock.patch.object(MODULE, "download_douyin_media_with_playwright") as playwright_mock,
        ):
            item = MODULE.build_item(
                "https://v.douyin.com/demo/",
                max_content_chars=2000,
                request_options=MODULE.RequestOptions(auto_login_douyin=True),
            )

        self.assertEqual(item["status"], "success")
        self.assertEqual(item["warning_count"], 0)
        self.assertEqual(item["extract_method"], "yt-dlp subtitles (retry.vtt)")
        self.assertEqual(item["title"], "登录后标题")
        self.assertEqual(item["author"], "疯码牛")
        login_mock.assert_called_once()
        playwright_mock.assert_not_called()

    def test_render_report_includes_status_summary(self) -> None:
        report = MODULE.render_report(
            "测试报告",
            [
                {
                    "title": "来源一",
                    "platform": "网页",
                    "source": "https://example.com/a",
                    "author": "作者A",
                    "published_at": "",
                    "duration": "",
                    "extract_method": "summarize",
                    "keywords": ["测试"],
                    "warnings": [],
                    "summary": "第一条摘要。",
                    "analysis": "核心价值：适合继续跟进。",
                    "analysis_method": "local heuristic",
                    "highlights": ["第一条高亮。"],
                    "content": "第一条原文内容。" * 20,
                    "status": "success",
                    "warning_count": 0,
                },
                {
                    "title": "来源二",
                    "platform": "网页",
                    "source": "https://example.com/b",
                    "author": "作者B",
                    "published_at": "",
                    "duration": "",
                    "extract_method": "html fallback",
                    "keywords": [],
                    "warnings": ["抓取失败"],
                    "summary": "第二条摘要。",
                    "analysis": "",
                    "analysis_method": "",
                    "highlights": [],
                    "content": "",
                    "status": "failed",
                    "warning_count": 1,
                },
            ],
            Path("/tmp/report"),
            "这批内容值得继续跟进。",
            "local heuristic",
        )
        self.assertIn("- 处理状态：partial", report)
        self.assertIn("- 成功：1", report)
        self.assertIn("- 失败：1", report)
        self.assertIn("### 分析", report)

    def test_build_output_options_auto_selects_obsidian_when_vault_configured(self) -> None:
        options = MODULE.build_output_options(Namespace(
            output_mode="auto",
            output_root="/tmp/out",
            obsidian_vault="/tmp/vault",
            obsidian_folder="Inbox/内容摘要",
        ))
        self.assertEqual(options.mode, "obsidian")
        self.assertEqual(options.obsidian_vault, "/tmp/vault")

    def test_build_output_options_rejects_obsidian_mode_without_vault(self) -> None:
        with self.assertRaises(ValueError):
            MODULE.build_output_options(Namespace(
                output_mode="obsidian",
                output_root="/tmp/out",
                obsidian_vault="",
                obsidian_folder="Inbox/内容摘要",
            ))

    def test_render_obsidian_index_note_includes_frontmatter_and_links(self) -> None:
        generated_at = MODULE.datetime(2026, 4, 18, 14, 30)
        note = MODULE.render_obsidian_index_note(
            "多平台信息汇总",
            [
                {
                    "title": "openai/openai-python",
                    "platform": "GitHub",
                    "platform_key": "github",
                    "author": "openai",
                    "status": "success",
                    "source": "https://github.com/openai/openai-python",
                    "summary": "这是仓库摘要。",
                    "analysis": "核心价值：适合继续跟进。",
                    "keywords": ["python", "sdk"],
                    "warnings": [],
                }
            ],
            [Path("sources/01_github_openai_openai-python.md")],
            "这批内容值得继续跟进。",
            "local heuristic",
            generated_at,
        )
        self.assertIn('type: "content-digest"', note)
        self.assertIn('tags:', note)
        self.assertIn("[openai/openai-python](sources/01_github_openai_openai-python.md)", note)
        self.assertIn("## 来源摘要", note)

    def test_write_obsidian_item_notes_creates_note_files(self) -> None:
        generated_at = MODULE.datetime(2026, 4, 18, 14, 30)
        item = {
            "title": "别以为你很难死去。",
            "platform": "微信公众号",
            "platform_key": "wechat",
            "status": "success",
            "source": "https://mp.weixin.qq.com/s/example",
            "author": "张荆棘",
            "published_at": "2026-04-18",
            "duration": "",
            "extract_method": "scrapling stealthy-fetch [#js_content]",
            "keywords": ["生死", "随笔"],
            "warnings": [],
            "summary": "这是摘要。",
            "analysis": "核心价值：值得归档。",
            "analysis_method": "local heuristic",
            "highlights": ["重点一。"],
            "content": "原文内容。" * 20,
        }
        with tempfile.TemporaryDirectory() as tmp:
            sources_dir = Path(tmp) / "sources"
            digest_path = Path(tmp) / "20260418_143000_多平台信息汇总.md"
            paths = MODULE.write_obsidian_item_notes([item], sources_dir, digest_path, generated_at)
            self.assertEqual(len(paths), 1)
            content = paths[0].read_text(encoding="utf-8")

        self.assertIn('type: "content-source"', content)
        self.assertIn("## 原文摘录", content)
        self.assertIn("[20260418_143000_多平台信息汇总](../20260418_143000_多平台信息汇总.md)", content)


if __name__ == "__main__":
    unittest.main()
