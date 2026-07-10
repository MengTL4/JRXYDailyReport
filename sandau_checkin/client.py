from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import requests

from .config import ReportConfig
from .signing import make_signature


TODAY_REPORT_URL = "https://reopen.sandau.edu.cn/report/report/todayReport"
MY_REPORT_URL = "https://reopen.sandau.edu.cn/report/report/getMyReport"
CURRENT_TIME_URL = "https://reopen.sandau.edu.cn/report/report/currentTime"


class SubmissionError(RuntimeError):
    """Raised when the submission result cannot be determined safely."""


class SubmissionStateUnknown(SubmissionError):
    """Raised when a submit request may have reached the server."""


@dataclass(frozen=True)
class SubmissionResult:
    success: bool
    message: str


@dataclass(frozen=True)
class HistoryResult:
    batchnos: tuple[str, ...]


class SandauClient:
    def __init__(self, session: requests.Session | Any | None = None) -> None:
        self._session = session or requests.Session()

    def submit(
        self, config: ReportConfig, timestamp_ms: int | None = None
    ) -> SubmissionResult:
        body = self._post_json(
            TODAY_REPORT_URL,
            config.to_payload(),
            config,
            timestamp_ms=timestamp_ms,
            operation="提交",
            unknown_state_on_network_error=True,
        )

        code = body.get("code")
        data = body.get("data")
        message = str(body.get("msg") or "").strip()
        if code == 0 and data != "error":
            return SubmissionResult(True, "打卡成功")
        if code == 0 and data == "error":
            return SubmissionResult(False, "更新失败或打卡通道已关闭")
        detail = f"，{message}" if message else ""
        return SubmissionResult(False, f"提交失败（code={code}{detail}）")

    def get_history(
        self, config: ReportConfig, timestamp_ms: int | None = None
    ) -> HistoryResult:
        body = self._post_json(
            MY_REPORT_URL,
            {"usercode": config.usercode, "batchno": ""},
            config,
            timestamp_ms=timestamp_ms,
            operation="查询历史",
        )
        self._require_success(body, "查询历史")
        data = body.get("data")
        if not isinstance(data, list):
            raise SubmissionError("查询历史失败：响应 data 不是数组")

        batchnos: set[str] = set()
        for item in data:
            if not isinstance(item, dict):
                raise SubmissionError("查询历史失败：记录格式无效")
            raw_batchno = item.get("batchno")
            if isinstance(raw_batchno, bool) or not isinstance(
                raw_batchno, (str, int)
            ):
                raise SubmissionError("查询历史失败：记录缺少有效 batchno")
            if item.get("usercode") != config.usercode:
                raise SubmissionError("查询历史失败：响应包含其他账号的记录")
            batchno = str(raw_batchno)
            try:
                datetime.strptime(batchno, "%Y%m%d")
            except ValueError as exc:
                raise SubmissionError("查询历史失败：记录日期格式无效") from exc
            batchnos.add(batchno)
        return HistoryResult(tuple(sorted(batchnos, reverse=True)))

    def get_server_batchno(
        self, config: ReportConfig, timestamp_ms: int | None = None
    ) -> str:
        body = self._post_json(
            CURRENT_TIME_URL,
            {},
            config,
            timestamp_ms=timestamp_ms,
            operation="查询服务器时间",
        )
        self._require_success(body, "查询服务器时间")
        value = body.get("data")
        if not isinstance(value, str):
            raise SubmissionError("查询服务器时间失败：响应 data 不是字符串")
        try:
            return datetime.fromisoformat(value).strftime("%Y%m%d")
        except ValueError as exc:
            raise SubmissionError("查询服务器时间失败：时间格式无效") from exc

    @staticmethod
    def _require_success(body: dict[str, Any], operation: str) -> None:
        code = body.get("code")
        if code == 0:
            return
        message = str(body.get("msg") or "").strip()
        detail = f"，{message}" if message else ""
        raise SubmissionError(f"{operation}失败（code={code}{detail}）")

    def _post_json(
        self,
        url: str,
        payload: dict[str, Any],
        config: ReportConfig,
        *,
        timestamp_ms: int | None,
        operation: str,
        unknown_state_on_network_error: bool = False,
    ) -> dict[str, Any]:
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
                url,
                json=payload,
                headers=headers,
                timeout=(5, 15),
            )
        except (requests.Timeout, requests.ConnectionError) as exc:
            if unknown_state_on_network_error:
                raise SubmissionStateUnknown(
                    "网络请求失败，提交状态未知；请先查询历史，避免重复提交"
                ) from exc
            raise SubmissionError(f"{operation}失败：网络请求错误") from exc
        except requests.RequestException as exc:
            if unknown_state_on_network_error:
                raise SubmissionStateUnknown(
                    "HTTP 请求异常，提交状态未知；请先查询历史，避免重复提交"
                ) from exc
            raise SubmissionError(f"{operation}失败：HTTP 请求错误") from exc

        if not 200 <= response.status_code < 300:
            if unknown_state_on_network_error:
                raise SubmissionStateUnknown(
                    f"服务器返回 HTTP {response.status_code}，提交状态未知"
                )
            raise SubmissionError(
                f"{operation}失败：服务器返回 HTTP {response.status_code}"
            )
        try:
            body = response.json()
        except ValueError as exc:
            if unknown_state_on_network_error:
                raise SubmissionStateUnknown(
                    "服务器响应不是 JSON，提交状态未知"
                ) from exc
            raise SubmissionError(f"{operation}失败：服务器响应不是 JSON") from exc
        if not isinstance(body, dict):
            if unknown_state_on_network_error:
                raise SubmissionStateUnknown(
                    "服务器响应不是 JSON 对象，提交状态未知"
                )
            raise SubmissionError(f"{operation}失败：服务器响应必须是 JSON 对象")
        return body
