import requests
import pytest

from sandau_checkin.client import SandauClient, SubmissionError
from sandau_checkin.config import ReportConfig


CONFIG = ReportConfig.from_dict(
    {
        "usercode": "TEST2026001",
        "username": "测试同学",
        "xy": "示例学院",
        "mobile": None,
        "auditor": "示例老师",
        "mdd": "示例校区>#1>101>1号床",
    }
)


class FakeResponse:
    def __init__(self, status_code=200, body=None, json_error=None):
        self.status_code = status_code
        self._body = body
        self._json_error = json_error

    def json(self):
        if self._json_error:
            raise self._json_error
        return self._body


class FakeSession:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if self.error:
            raise self.error
        return self.response


def test_submit_sends_expected_request_once():
    session = FakeSession(FakeResponse(body={"code": 0, "msg": "", "data": ""}))
    client = SandauClient(session=session)

    result = client.submit(CONFIG, timestamp_ms=1700000000123)

    assert result.success is True
    assert result.message == "打卡成功"
    assert len(session.calls) == 1
    url, request = session.calls[0]
    assert url.endswith("/report/report/todayReport")
    assert request["json"] == CONFIG.to_payload()
    assert request["timeout"] == (5, 15)
    assert request["headers"]["ts"] == "1700000000123"
    assert request["headers"]["decodes"] == "5C2A01D4F0F744B7080E3720DE93B986"
    assert "Cookie" not in request["headers"]


def test_channel_closed_is_not_success():
    session = FakeSession(FakeResponse(body={"code": 0, "msg": "", "data": "error"}))

    result = SandauClient(session=session).submit(CONFIG)

    assert result.success is False
    assert "通道" in result.message


def test_server_code_is_not_success():
    session = FakeSession(FakeResponse(body={"code": 500, "msg": "提交失败", "data": None}))

    result = SandauClient(session=session).submit(CONFIG)

    assert result.success is False
    assert "500" in result.message
    assert "提交失败" in result.message


@pytest.mark.parametrize("error", [requests.Timeout(), requests.ConnectionError()])
def test_network_error_has_unknown_state_warning(error):
    session = FakeSession(error=error)

    with pytest.raises(SubmissionError, match="状态未知"):
        SandauClient(session=session).submit(CONFIG)


def test_non_2xx_is_an_error():
    session = FakeSession(FakeResponse(status_code=503, body={"code": 0}))

    with pytest.raises(SubmissionError, match="HTTP 503"):
        SandauClient(session=session).submit(CONFIG)


def test_non_json_is_an_error():
    session = FakeSession(FakeResponse(json_error=ValueError("not json")))

    with pytest.raises(SubmissionError, match="不是 JSON"):
        SandauClient(session=session).submit(CONFIG)


def test_non_object_json_is_an_error():
    session = FakeSession(FakeResponse(body=[]))

    with pytest.raises(SubmissionError, match="JSON 对象"):
        SandauClient(session=session).submit(CONFIG)


def test_get_history_returns_unique_dates_in_reverse_order():
    session = FakeSession(
        FakeResponse(
            body={
                "code": 0,
                "msg": "",
                "data": [
                    {"batchno": 20260708, "usercode": CONFIG.usercode},
                    {"batchno": "20260710", "usercode": CONFIG.usercode},
                    {"batchno": 20260710, "usercode": CONFIG.usercode},
                ],
            }
        )
    )

    history = SandauClient(session=session).get_history(
        CONFIG, timestamp_ms=1700000000123
    )

    assert history.batchnos == ("20260710", "20260708")
    url, request = session.calls[0]
    assert url.endswith("/report/report/getMyReport")
    assert request["json"] == {"usercode": CONFIG.usercode, "batchno": ""}
    assert request["headers"]["ts"] == "1700000000123"
    assert "Cookie" not in request["headers"]


def test_get_history_rejects_invalid_record_date():
    session = FakeSession(
        FakeResponse(
            body={
                "code": 0,
                "msg": "",
                "data": [{"batchno": "today", "usercode": CONFIG.usercode}],
            }
        )
    )

    with pytest.raises(SubmissionError, match="日期格式无效"):
        SandauClient(session=session).get_history(CONFIG)


def test_get_history_rejects_other_account_record():
    session = FakeSession(
        FakeResponse(
            body={
                "code": 0,
                "msg": "",
                "data": [{"batchno": 20260710, "usercode": "OTHER"}],
            }
        )
    )

    with pytest.raises(SubmissionError, match="其他账号"):
        SandauClient(session=session).get_history(CONFIG)


def test_get_history_rejects_non_list_data():
    session = FakeSession(FakeResponse(body={"code": 0, "msg": "", "data": {}}))

    with pytest.raises(SubmissionError, match="data 不是数组"):
        SandauClient(session=session).get_history(CONFIG)


def test_get_history_rejects_server_error():
    session = FakeSession(
        FakeResponse(body={"code": 500, "msg": "查询失败", "data": None})
    )

    with pytest.raises(SubmissionError, match="500.*查询失败"):
        SandauClient(session=session).get_history(CONFIG)


def test_get_server_batchno_uses_school_server_date():
    session = FakeSession(
        FakeResponse(body={"code": 0, "msg": "", "data": "2026-07-10 11:09:33"})
    )

    batchno = SandauClient(session=session).get_server_batchno(
        CONFIG, timestamp_ms=1700000000123
    )

    assert batchno == "20260710"
    url, request = session.calls[0]
    assert url.endswith("/report/report/currentTime")
    assert request["json"] == {}
    assert request["headers"]["ts"] == "1700000000123"


def test_get_server_batchno_rejects_invalid_time():
    session = FakeSession(
        FakeResponse(body={"code": 0, "msg": "", "data": "not-a-time"})
    )

    with pytest.raises(SubmissionError, match="时间格式无效"):
        SandauClient(session=session).get_server_batchno(CONFIG)
