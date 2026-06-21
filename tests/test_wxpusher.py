import os
import unittest
from unittest.mock import Mock, patch

from service.notifications.wxpusher import _get_wxpusher_uids, _parse_wxpusher_uids, send_wxpusher


class WxPusherTests(unittest.TestCase):
    def test_parse_wxpusher_uids_strips_and_dedupes(self):
        self.assertEqual(
            _parse_wxpusher_uids(" UID_1,UID_2 , UID_1 ,, UID_3 "),
            ["UID_1", "UID_2", "UID_3"],
        )

    def test_get_wxpusher_uids_prefers_multi_uid_env(self):
        with patch.dict(
            os.environ,
            {
                "WXPUSHER_UIDS": "UID_A, UID_B",
                "WXPUSHER_UID": "UID_LEGACY",
            },
            clear=True,
        ):
            self.assertEqual(_get_wxpusher_uids(), ["UID_A", "UID_B"])

    def test_get_wxpusher_uids_falls_back_to_legacy_single_uid(self):
        with patch.dict(os.environ, {"WXPUSHER_UID": "UID_LEGACY"}, clear=True):
            self.assertEqual(_get_wxpusher_uids(), ["UID_LEGACY"])

    def test_send_wxpusher_posts_to_multiple_uids(self):
        fake_response = Mock()
        fake_response.raise_for_status.return_value = None
        fake_response.json.return_value = {"success": True}

        with patch.dict(
            os.environ,
            {
                "WXPUSHER_APP_TOKEN": "test-token",
                "WXPUSHER_UIDS": "UID_A, UID_B, UID_A",
            },
            clear=True,
        ):
            with patch("service.notifications.wxpusher.requests.post", return_value=fake_response) as mock_post:
                ok = send_wxpusher("标题", "内容", content_type=3)

        self.assertTrue(ok)
        self.assertEqual(
            mock_post.call_args.kwargs["json"],
            {
                "appToken": "test-token",
                "content": "内容",
                "summary": "标题",
                "contentType": 3,
                "uids": ["UID_A", "UID_B"],
            },
        )

    def test_send_wxpusher_returns_false_when_uid_config_missing(self):
        with patch.dict(os.environ, {"WXPUSHER_APP_TOKEN": "test-token"}, clear=True):
            self.assertFalse(send_wxpusher("标题", "内容"))


if __name__ == "__main__":
    unittest.main()
