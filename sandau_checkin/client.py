from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

from .config import ReportConfig
from .signing import make_signature


TODAY_REPORT_URL = "https://reopen.sandau.edu.cn/report/report/todayReport"


class SubmissionError(RuntimeError):
    """Raised when the submission result cannot be determined safely."""


@dataclass(frozen=True)
class SubmissionResult:
    success: bool
    message: str


class SandauClient:
    def __init__(self, session: requests.Session | Any | None = None) -> None:
        self._session = session or requests.Session()

    def submit(
        self, config: ReportConfig, timestamp_ms: int | None = None
    ) -> SubmissionResult:
        signature = make_signature(config.usercode, timestamp_ms=timestamp_ms)
        headers = {
            "Accept": "*/*",
            "Content-Type": "application/json",
            "Origin": "https://reopen.sandau.edu.cn",
            "Referer": "https://reopen.sandau.edu.cn/allApps/",
            "User-Agent": (
                "Mozilla/5.0 (Linux; Android 16) AppleWebKit/537.36 "
                "Chrome/138.0.0.0 Mobile Safari/537.36"
            ),
            "X-Requested-With": "com.wisedu.cpdaily",
            "ts": signature.ts,
            "decodes": signature.decodes,
        }
        try:
            response = self._session.post(
                TODAY_REPORT_URL,
                json=config.to_payload(),
                headers=headers,
                timeout=(5, 15),
            )
        except (requests.Timeout, requests.ConnectionError) as exc:
            raise SubmissionError(
                "网络请求失败，提交状态未知；请先手动查询，避免重复提交"
            ) from exc
        except requests.RequestException as exc:
            raise SubmissionError("HTTP 请求失败，未自动重试") from exc

        if not 200 <= response.status_code < 300:
            raise SubmissionError(f"服务器返回 HTTP {response.status_code}")
        try:
            body = response.json()
        except ValueError as exc:
            raise SubmissionError("服务器响应不是 JSON") from exc
        if not isinstance(body, dict):
            raise SubmissionError("服务器响应必须是 JSON 对象")

        code = body.get("code")
        data = body.get("data")
        message = str(body.get("msg") or "").strip()
        if code == 0 and data != "error":
            return SubmissionResult(True, "打卡成功")
        if code == 0 and data == "error":
            return SubmissionResult(False, "更新失败或打卡通道已关闭")
        detail = f"，{message}" if message else ""
        return SubmissionResult(False, f"提交失败（code={code}{detail}）")
