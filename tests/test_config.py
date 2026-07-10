import json

import pytest

from sandau_checkin.config import ConfigError, ReportConfig


VALID = {
    "usercode": "TEST2026001",
    "username": "测试同学",
    "xy": "示例学院",
    "mobile": None,
    "auditor": "示例老师",
    "mdd": "示例校区>#1>101>1号床",
}


def test_loads_valid_config(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(VALID, ensure_ascii=False), encoding="utf-8")

    config = ReportConfig.from_file(path)

    assert config.to_payload() == VALID


@pytest.mark.parametrize("field", ["usercode", "username", "xy", "auditor", "mdd"])
def test_rejects_missing_or_blank_required_field(tmp_path, field):
    data = dict(VALID)
    data[field] = "  "
    path = tmp_path / "config.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ConfigError, match=field):
        ReportConfig.from_file(path)


def test_rejects_non_string_mobile(tmp_path):
    data = dict(VALID, mobile=123)
    path = tmp_path / "config.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ConfigError, match="mobile"):
        ReportConfig.from_file(path)


def test_redacted_summary_does_not_expose_full_identity():
    config = ReportConfig.from_dict(VALID)

    summary = config.redacted_summary()

    assert "6001" in summary
    assert VALID["usercode"] not in summary
    assert VALID["username"] not in summary
    assert "测**" in summary
    assert VALID["xy"] in summary
