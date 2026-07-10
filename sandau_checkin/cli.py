from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence

from .client import SandauClient, SubmissionError
from .config import ConfigError, ReportConfig


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="提交一次杉达学院假期打卡")
    parser.add_argument("--config", default="config.json", help="打卡 JSON 配置路径")
    parser.add_argument("--yes", action="store_true", help="跳过交互确认")
    return parser


def run(
    argv: Sequence[str] | None = None,
    *,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
    error_fn: Callable[[str], None] = lambda text: print(text, file=sys.stderr),
    client_factory: Callable[[], SandauClient] = SandauClient,
) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = ReportConfig.from_file(args.config)
    except ConfigError as exc:
        error_fn(f"配置错误：{exc}")
        return 2

    output_fn(config.redacted_summary())
    if not args.yes:
        answer = input_fn("确认提交一次打卡？输入 yes 继续: ").strip().lower()
        if answer != "yes":
            output_fn("已取消，未发送请求")
            return 0

    try:
        result = client_factory().submit(config)
    except SubmissionError as exc:
        error_fn(f"提交失败：{exc}")
        return 1

    if result.success:
        output_fn(result.message)
        return 0
    error_fn(result.message)
    return 1


def main() -> None:
    raise SystemExit(run())
