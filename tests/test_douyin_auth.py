import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "douyin_auth.py"
SPEC = importlib.util.spec_from_file_location("douyin_auth", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class DouyinAuthTests(unittest.TestCase):
    def test_has_login_markers_detects_session_cookie(self) -> None:
        self.assertTrue(MODULE.has_login_markers([
            {"name": "ttwid", "value": "a"},
            {"name": "sessionid", "value": "b"},
        ]))
        self.assertFalse(MODULE.has_login_markers([
            {"name": "ttwid", "value": "a"},
            {"name": "s_v_web_id", "value": "b"},
        ]))

    def test_write_netscape_cookie_file_writes_header_and_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "cookies.txt"
            MODULE.write_netscape_cookie_file([
                {
                    "domain": ".douyin.com",
                    "path": "/",
                    "secure": True,
                    "expires": 123,
                    "name": "sessionid",
                    "value": "secret",
                }
            ], target)
            content = target.read_text(encoding="utf-8")

        self.assertIn("# Netscape HTTP Cookie File", content)
        self.assertIn(".douyin.com\tTRUE\t/\tTRUE\t123\tsessionid\tsecret", content)

    def test_try_extract_media_urls_from_payload_collects_nested_url_lists(self) -> None:
        payload = {
            "aweme_detail": {
                "video": {
                    "play_addr": {
                        "url_list": [
                            "https://media.example.com/a.mp4",
                            "https://media.example.com/b.mp4",
                        ]
                    },
                    "bit_rate": [
                        {
                            "play_addr": {
                                "url_list": [
                                    "https://media.example.com/c.mp4",
                                    "https://media.example.com/a.mp4",
                                ]
                            }
                        }
                    ],
                }
            }
        }
        urls = MODULE.try_extract_media_urls_from_payload(payload)
        self.assertEqual(urls, [
            "https://media.example.com/a.mp4",
            "https://media.example.com/b.mp4",
            "https://media.example.com/c.mp4",
        ])

    def test_choose_primary_media_url_prefers_video_over_images(self) -> None:
        primary = MODULE.choose_primary_media_url([
            "https://p3-pc.douyinpic.com/avatar.jpeg",
            "https://sf6-cdn-tos.douyinstatic.com/obj/ies-music/1.mp3",
            "https://www.douyin.com/aweme/v1/play/?video_id=123",
        ])
        self.assertEqual(primary, "https://www.douyin.com/aweme/v1/play/?video_id=123")


if __name__ == "__main__":
    unittest.main()
