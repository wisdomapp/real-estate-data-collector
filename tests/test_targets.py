from __future__ import annotations

import unittest

from SUUMO_SCRAPER.targets import discover_paginated_urls


class DiscoverPaginatedUrlsTests(unittest.TestCase):
    def test_returns_base_url_only_when_no_pagination_exists(self) -> None:
        urls = discover_paginated_urls(
            "https://suumo.jp/ms/chuko/tokyo/sc_example/",
            "<html><body>No pager</body></html>",
        )

        self.assertEqual(
            urls,
            ["https://suumo.jp/ms/chuko/tokyo/sc_example/"],
        )

    def test_expands_to_last_page_found(self) -> None:
        html_text = """
        <a href="/ms/chuko/tokyo/sc_example/?page=2">2</a>
        <a href="/ms/chuko/tokyo/sc_example/?page=5">5</a>
        <a href="/ms/chuko/tokyo/sc_example/?page=3">3</a>
        """

        urls = discover_paginated_urls(
            "https://suumo.jp/ms/chuko/tokyo/sc_example/",
            html_text,
        )

        self.assertEqual(
            urls,
            [
                "https://suumo.jp/ms/chuko/tokyo/sc_example/",
                "https://suumo.jp/ms/chuko/tokyo/sc_example/?page=2",
                "https://suumo.jp/ms/chuko/tokyo/sc_example/?page=3",
                "https://suumo.jp/ms/chuko/tokyo/sc_example/?page=4",
                "https://suumo.jp/ms/chuko/tokyo/sc_example/?page=5",
            ],
        )


if __name__ == "__main__":
    unittest.main()
