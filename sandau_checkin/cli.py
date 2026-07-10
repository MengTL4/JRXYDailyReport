from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Callable, Sequence

from .client import (
    HistoryResult,
    SandauClient,
    SubmissionError,
    SubmissionStateUnknown,
)
from .config import ConfigError, ReportConfig


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="提交一次杉达学院假期打卡")
    parser.add_argument("--config", default="config.json", help="打卡 JSON 配置路径")
    parser.add_argument("--yes", action="store_true", help="跳过交互确认")
    parser.add_argument(
        "--history", action="store_true", help="只查询并显示当前账号的打卡历史"
    )
    return parser


def format_batchno(batchno: str) -> str:
    return f"{batchno[:4]}-{batchno[4:6]}-{batchno[6:]}"


def format_history(history: HistoryResult) -> list[str]:
    if not history.batchnos:
        return ["暂无历史打卡记录"]
    lines = [f"历史打卡记录（共 {len(history.batchnos)} 天）："]
    lines.extend(f"- {format_batchno(batchno)}" for batchno in history.batchnos)
    return lines


def verify_current_report(
    client: SandauClient,
    config: ReportConfig,
    *,
    attempts: int = 3,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> str:
    current_batchno = client.get_server_batchno(config)
    last_error: SubmissionError | None = None
    for attempt in range(attempts):
        try:
            history = client.get_history(config)
        except SubmissionError as exc:
            last_error = exc
        else:
            last_error = None
            if current_batchno in history.batchnos:
                return current_batchno
        if attempt + 1 < attempts:
            sleep_fn(1.0)

    if last_error is not None:
        raise SubmissionError(f"历史查询未能完成：{last_error}") from last_error
    raise SubmissionError(
        f"历史记录中未找到 {format_batchno(current_batchno)} 的打卡"
    )


def run(
    argv: Sequence[str] | None = None,
    *,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
    error_fn: Callable[[str], None] = lambda text: print(text, file=sys.stderr),
    client_factory: Callable[[], SandauClient] = SandauClient,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = ReportConfig.from_file(args.config)
    except ConfigError as exc:
        error_fn(f"配置错误：{exc}")
        return 2

    output_fn(config.redacted_summary())

    if args.history:
        client = client_factory()
        try:
            history = client.get_history(config)
        except SubmissionError as exc:
            error_fn(f"历史查询失败：{exc}")
            return 1
        for line in format_history(history):
            output_fn(line)
        return 0

    if not args.yes:
        answer = input_fn("确认提交一次打卡？输入 yes 继续: ").strip().lower()
        if answer != "yes":
            output_fn("已取消，未发送请求")
            return 0

    client = client_factory()
    try:
        result = client.submit(config)
    except SubmissionStateUnknown as exc:
        try:
            current_batchno = verify_current_report(
                client, config, sleep_fn=sleep_fn
            )
        except SubmissionError as verify_exc:
            error_fn(f"{exc}；历史确认失败：{verify_exc}")
            return 1
        output_fn(
            "提交响应未知，但今日打卡已在历史记录确认"
            f"（{format_batchno(current_batchno)}）"
        )
        return 0
    except SubmissionError as exc:
        error_fn(f"提交失败：{exc}")
        return 1

    if not result.success:
        error_fn(result.message)
        return 1

    try:
        current_batchno = verify_current_report(client, config, sleep_fn=sleep_fn)
    except SubmissionError as exc:
        error_fn(f"提交接口返回成功，但历史确认失败：{exc}；请勿立即重复提交")
        return 1

    output_fn(f"打卡成功，历史记录已确认（{format_batchno(current_batchno)}）")
    return 0


def main() -> None:
    raise SystemExit(run())
