import importlib.util
import sys
import tempfile
import unittest
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


if __name__ == "__main__":
    unittest.main()
