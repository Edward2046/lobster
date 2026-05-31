import os
import unittest
from unittest.mock import patch

from service.tools.web_search_tool import search_web


class WebSearchToolTests(unittest.TestCase):
    def test_missing_api_key_returns_helpful_message(self):
        with patch.dict(os.environ, {}, clear=True):
            result = search_web("ai news")
        self.assertIn("TAVILY_API_KEY is not set", result)

    def test_search_success_formats_markdown_results(self):
        class FakeTavilyClient:
            def search(self, query, max_results=5):
                return {
                    "results": [
                        {"title": "Title 1", "url": "https://example.com/1", "content": "Summary 1"},
                        {"title": "Title 2", "url": "https://example.com/2", "content": "Summary 2"},
                    ]
                }

        with patch.dict(os.environ, {"TAVILY_API_KEY": "test-key"}, clear=True):
            with patch("service.tools.web_search_tool._create_tavily_client", return_value=FakeTavilyClient()):
                result = search_web("ai news", max_results=2)

        self.assertIn("1. [Title 1](https://example.com/1)", result)
        self.assertIn("Summary 1", result)
        self.assertIn("2. [Title 2](https://example.com/2)", result)
        self.assertIn("Summary 2", result)

    def test_search_failure_returns_helpful_message(self):
        class FakeTavilyClient:
            def search(self, query, max_results=5):
                raise RuntimeError("network down")

        with patch.dict(os.environ, {"TAVILY_API_KEY": "test-key"}, clear=True):
            with patch("service.tools.web_search_tool._create_tavily_client", return_value=FakeTavilyClient()):
                result = search_web("ai news")

        self.assertIn("Web search failed with Tavily", result)


if __name__ == "__main__":
    unittest.main()
