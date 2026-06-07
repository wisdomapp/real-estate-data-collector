from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Any

import requests


# 不動産情報ライブラリ 公開API
# エンドポイント例: https://www.reinfolib.mlit.go.jp/ex-api/external/XIT001
API_BASE_URL = "https://www.reinfolib.mlit.go.jp/ex-api/external"
# XIT001: 不動産価格（取引価格・成約価格）情報取得API
TRANSACTION_ENDPOINT = "XIT001"
# APIキーは Azure API Management のヘッダで渡す
API_KEY_HEADER = "Ocp-Apim-Subscription-Key"

DEFAULT_USER_AGENT = "reinfolib-research-client/0.1 (real-estate price study)"

# 価格情報区分 priceClassification:
#   "01" = 取引価格情報（2005年Q3以降・件数多） / "02" = 成約価格情報（2021年Q1以降・レインズ由来）
#   成約価格だけが欲しい場合は "02"。未指定なら両方取得し、各レコードの PriceCategory で判別できる。
PRICE_CLASSIFICATION_CHOICES = ("01", "02")


class ReinfolibError(RuntimeError):
    """reinfolib API が想定外の応答を返したときに送出する。"""


@dataclass(slots=True)
class ClientConfig:
    api_key: str
    timeout_seconds: int = 30
    sleep_seconds: float = 1.0
    max_retries: int = 4
    backoff_base_seconds: float = 2.0
    user_agent: str = DEFAULT_USER_AGENT


class ReinfolibClient:
    """成約価格・取引価格情報を取得するクライアント。

    - 429 / 5xx / 接続エラーは指数バックオフ（ジッター付き）でリトライ
    - レスポンスごとに status を検証し、想定外なら ReinfolibError
    - 連続アクセス時はリクエスト間に sleep（負荷配慮）
    """

    def __init__(self, config: ClientConfig) -> None:
        if not config.api_key:
            raise ReinfolibError(
                "API key is empty. Set REINFOLIB_API_KEY env var or pass --api-key."
            )
        self._config = config
        self._session = requests.Session()
        self._session.headers.update(
            {
                API_KEY_HEADER: config.api_key,
                "User-Agent": config.user_agent,
            }
        )

    def fetch_transactions(
        self,
        *,
        year: int,
        quarter: int | None = None,
        area: str | None = None,
        city: str | None = None,
        station: str | None = None,
        price_classification: str | None = None,
        language: str = "ja",
    ) -> list[dict[str, Any]]:
        """1 回分（年・四半期・エリア等で絞った単位）の取引データを取得する。"""
        params: dict[str, str] = {"year": str(year)}
        if quarter is not None:
            params["quarter"] = str(quarter)
        if area:
            params["area"] = area
        if city:
            params["city"] = city
        if station:
            params["station"] = station
        if price_classification:
            params["priceClassification"] = price_classification
        if language:
            params["language"] = language

        payload = self._get(TRANSACTION_ENDPOINT, params)
        status = payload.get("status")
        # 正常時の status は "OK"。マニュアルの版差を考慮し None は許容する。
        if status not in ("OK", None):
            raise ReinfolibError(f"API status not OK: {status!r} (params={params})")
        data = payload.get("data")
        if data is None:
            raise ReinfolibError(
                f"Response has no 'data' field (params={params}, keys={list(payload)})"
            )
        if not isinstance(data, list):
            raise ReinfolibError(f"'data' is not a list (params={params})")
        return data

    def _get(self, endpoint: str, params: dict[str, str]) -> dict[str, Any]:
        url = f"{API_BASE_URL}/{endpoint}"
        last_error: Exception | None = None

        for attempt in range(1, self._config.max_retries + 1):
            try:
                response = self._session.get(
                    url, params=params, timeout=self._config.timeout_seconds
                )
            except requests.RequestException as exc:  # 接続/タイムアウト系
                last_error = exc
            else:
                if response.status_code == 200:
                    self._sleep()
                    try:
                        return response.json()
                    except ValueError as exc:
                        raise ReinfolibError(
                            f"Response body was not valid JSON (params={params})"
                        ) from exc
                if response.status_code in (429, 500, 502, 503, 504):
                    last_error = ReinfolibError(
                        f"HTTP {response.status_code} (params={params})"
                    )
                else:
                    # 4xx（認証・パラメータ誤り等）は即時失敗（リトライしても無駄）
                    raise ReinfolibError(
                        f"HTTP {response.status_code}: {response.text[:200]} (params={params})"
                    )

            backoff = self._config.backoff_base_seconds * (2 ** (attempt - 1))
            backoff += random.uniform(0, 1.0)
            time.sleep(backoff)

        raise ReinfolibError(
            f"Exhausted {self._config.max_retries} retries (params={params}): {last_error}"
        )

    def _sleep(self) -> None:
        time.sleep(self._config.sleep_seconds + random.uniform(0, 0.5))
