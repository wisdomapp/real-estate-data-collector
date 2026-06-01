"""国土交通省「不動産情報ライブラリ」公開APIのクライアント。

価格バックボーン（成約価格・取引価格）を合法・公式APIで取得するための最小実装。
スクレイピングではなく公式APIなので robots.txt / 規約上の懸念が無い。
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
