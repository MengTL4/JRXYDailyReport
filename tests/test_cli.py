import json

from sandau_checkin.cli import run
from sandau_checkin.client import (
    HistoryResult,
    SubmissionError,
    SubmissionResult,
    SubmissionStateUnknown,
)


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
        submit_calls = 0
        history_calls = 0

        def submit(self, config):
            self.submit_calls += 1
            assert config.usercode == DATA["usercode"]
            return SubmissionResult(True, "打卡成功")

        def get_server_batchno(self, config):
            return "20260710"

        def get_history(self, config):
            self.history_calls += 1
            return HistoryResult(("20260710", "20260708"))

    client = FakeClient()
    code = run(
        ["--config", str(path), "--yes"],
        input_fn=lambda _: "unused",
        output_fn=output.append,
        error_fn=output.append,
        client_factory=lambda: client,
    )

    assert code == 0
    assert client.submit_calls == 1
    assert client.history_calls == 1
    assert output[-1] == "打卡成功，历史记录已确认（2026-07-10）"


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
        sleep_fn=lambda _: None,
    )

    assert code == 1
    assert errors == ["通道已关闭"]


def test_history_mode_lists_dates_without_submitting(tmp_path):
    path = write_config(tmp_path)
    output = []

    class FakeClient:
        def submit(self, config):
            raise AssertionError("history mode must not submit")

        def get_history(self, config):
            return HistoryResult(("20260710", "20260708"))

    code = run(
        ["--config", str(path), "--history"],
        output_fn=output.append,
        error_fn=output.append,
        client_factory=FakeClient,
    )

    assert code == 0
    assert "历史打卡记录（共 2 天）：" in output
    assert "- 2026-07-10" in output
    assert "- 2026-07-08" in output


def test_history_mode_handles_empty_history(tmp_path):
    path = write_config(tmp_path)
    output = []

    class FakeClient:
        def get_history(self, config):
            return HistoryResult(())

    code = run(
        ["--config", str(path), "--history"],
        output_fn=output.append,
        error_fn=output.append,
        client_factory=FakeClient,
    )

    assert code == 0
    assert output[-1] == "暂无历史打卡记录"


def test_success_requires_current_day_in_history(tmp_path):
    path = write_config(tmp_path)
    errors = []

    class FakeClient:
        def submit(self, config):
            return SubmissionResult(True, "打卡成功")

        def get_server_batchno(self, config):
            return "20260710"

        def get_history(self, config):
            return HistoryResult(("20260708",))

    code = run(
        ["--config", str(path), "--yes"],
        output_fn=lambda _: None,
        error_fn=errors.append,
        client_factory=FakeClient,
        sleep_fn=lambda _: None,
    )

    assert code == 1
    assert "未找到 2026-07-10" in errors[-1]
    assert "请勿立即重复提交" in errors[-1]


def test_verification_error_is_not_reported_as_success(tmp_path):
    path = write_config(tmp_path)
    output = []
    errors = []

    class FakeClient:
        def submit(self, config):
            return SubmissionResult(True, "打卡成功")

        def get_server_batchno(self, config):
            raise SubmissionError("查询服务器时间失败：网络请求错误")

    code = run(
        ["--config", str(path), "--yes"],
        output_fn=output.append,
        error_fn=errors.append,
        client_factory=FakeClient,
    )

    assert code == 1
    assert not any("打卡成功" in line for line in output)
    assert "历史确认失败" in errors[-1]


def test_verification_retries_read_only_history(tmp_path):
    path = write_config(tmp_path)
    output = []

    class FakeClient:
        history_calls = 0

        def submit(self, config):
            return SubmissionResult(True, "打卡成功")

        def get_server_batchno(self, config):
            return "20260710"

        def get_history(self, config):
            self.history_calls += 1
            if self.history_calls == 1:
                return HistoryResult(("20260708",))
            return HistoryResult(("20260710", "20260708"))

    client = FakeClient()
    code = run(
        ["--config", str(path), "--yes"],
        output_fn=output.append,
        error_fn=output.append,
        client_factory=lambda: client,
        sleep_fn=lambda _: None,
    )

    assert code == 0
    assert client.history_calls == 2
    assert output[-1] == "打卡成功，历史记录已确认（2026-07-10）"


def test_unknown_submit_response_can_be_confirmed_from_history(tmp_path):
    path = write_config(tmp_path)
    output = []

    class FakeClient:
        def submit(self, config):
            raise SubmissionStateUnknown("提交状态未知")

        def get_server_batchno(self, config):
            return "20260710"

        def get_history(self, config):
            return HistoryResult(("20260710",))

    code = run(
        ["--config", str(path), "--yes"],
        output_fn=output.append,
        error_fn=output.append,
        client_factory=FakeClient,
        sleep_fn=lambda _: None,
    )

    assert code == 0
    assert "提交响应未知，但今日打卡已在历史记录确认" in output[-1]
