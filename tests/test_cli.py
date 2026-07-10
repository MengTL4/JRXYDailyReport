import json

from sandau_checkin.cli import run
from sandau_checkin.client import SubmissionResult


DATA = {
    "usercode": "TEST2026001",
    "username": "测试同学",
    "xy": "示例学院",
    "mobile": None,
    "auditor": "示例老师",
    "mdd": "示例校区>#1>101>1号床",
}


def write_config(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(DATA, ensure_ascii=False), encoding="utf-8")
    return path


def test_cancel_does_not_construct_client(tmp_path):
    path = write_config(tmp_path)
    output = []

    def forbidden_factory():
        raise AssertionError("client must not be created after cancellation")

    code = run(
        ["--config", str(path)],
        input_fn=lambda _: "no",
        output_fn=output.append,
        error_fn=output.append,
        client_factory=forbidden_factory,
    )

    assert code == 0
    assert any("已取消" in line for line in output)


def test_yes_flag_submits_exactly_once(tmp_path):
    path = write_config(tmp_path)
    output = []

    class FakeClient:
        calls = 0

        def submit(self, config):
            self.calls += 1
            assert config.usercode == DATA["usercode"]
            return SubmissionResult(True, "打卡成功")

    client = FakeClient()
    code = run(
        ["--config", str(path), "--yes"],
        input_fn=lambda _: "unused",
        output_fn=output.append,
        error_fn=output.append,
        client_factory=lambda: client,
    )

    assert code == 0
    assert client.calls == 1
    assert output[-1] == "打卡成功"


def test_failed_result_returns_nonzero(tmp_path):
    path = write_config(tmp_path)

    class FakeClient:
        def submit(self, config):
            return SubmissionResult(False, "通道已关闭")

    errors = []
    code = run(
        ["--config", str(path), "--yes"],
        output_fn=lambda _: None,
        error_fn=errors.append,
        client_factory=FakeClient,
    )

    assert code == 1
    assert errors == ["通道已关闭"]
