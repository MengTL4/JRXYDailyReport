from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any


class ConfigError(ValueError):
    """Raised when the report configuration cannot be used safely."""


@dataclass(frozen=True)
class ReportConfig:
    usercode: str
    username: str
    xy: str
    mobile: str | None
    auditor: str
    mdd: str

    @classmethod
    def from_file(cls, path: str | Path) -> "ReportConfig":
        config_path = Path(path)
        try:
            raw = config_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ConfigError(f"无法读取配置文件: {config_path}") from exc
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ConfigError(f"配置文件不是有效 JSON: {config_path}") from exc
        if not isinstance(data, dict):
            raise ConfigError("配置根节点必须是 JSON 对象")
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReportConfig":
        required = ("usercode", "username", "xy", "auditor", "mdd")
        values: dict[str, str] = {}
        for field in required:
            value = data.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ConfigError(f"字段 {field} 必须是非空字符串")
            values[field] = value.strip()

        if "mobile" not in data:
            raise ConfigError("缺少字段 mobile；无号码时请填写 null")
        mobile = data["mobile"]
        if mobile is not None and not isinstance(mobile, str):
            raise ConfigError("字段 mobile 必须是字符串或 null")

        return cls(mobile=mobile.strip() if isinstance(mobile, str) else None, **values)

    def to_payload(self) -> dict[str, str | None]:
        return asdict(self)

    def redacted_summary(self) -> str:
        suffix = self.usercode[-4:]
        masked_usercode = f"****{suffix}"
        masked_name = f"{self.username[0]}**"
        return f"学号: {masked_usercode}，姓名: {masked_name}，学院: {self.xy}"
