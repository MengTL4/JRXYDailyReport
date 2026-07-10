# 假期打卡脚本

纯 Python 的单次提交工具，不登录、不保存 Cookie，也不会自动重试提交请求。

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

检查脱敏摘要，输入 `yes` 后脚本才会发送一次请求。提交接口返回成功后，脚本会使用学校服务器日期查询当前账号的打卡历史；只有历史中确实存在当天记录，才显示“打卡成功”。

`--yes` 可跳过确认，但首版不包含定时任务：

```powershell
uv run python -m sandau_checkin --config config.json --yes
```

## 查询打卡历史

只查询当前配置账号的历史记录，不会发送打卡请求：

```powershell
uv run python -m sandau_checkin --config config.json --history
```

输出只包含脱敏账号摘要、记录总数和打卡日期，不显示完整学号、姓名、手机号、宿舍或 Cookie。

为应对历史数据的短暂同步延迟，提交后最多重查三次只读历史接口。提交请求本身始终只发送一次；如果提交响应未知但当天记录已出现在历史中，脚本会明确说明已从历史确认。若仍无法确认，程序返回非零退出码并提示不要立即重复提交。
