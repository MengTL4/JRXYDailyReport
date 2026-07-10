# 杉达假期打卡脚本

纯 Python 的单次提交工具，不登录、不保存 Cookie，也不会自动重试 POST。

## 安装

```powershell
uv sync
Copy-Item config.example.json config.json
```

编辑 `config.json`，填入本人的学号、姓名、学院、辅导员和目的地/宿舍信息。没有联系电话时保留 `null`。

## 运行一次

```powershell
uv run python -m sandau_checkin --config config.json
```

检查脱敏摘要，输入 `yes` 后脚本才会发送一次请求。只有接口返回 `code == 0` 且 `data != "error"` 才显示“打卡成功”。

`--yes` 可跳过确认，但首版不包含定时任务：

```powershell
uv run python -m sandau_checkin --config config.json --yes
```

网络异常时脚本不会自动重试，因为无法确定服务器是否已经收到第一次提交；请先在学校页面查询状态。
