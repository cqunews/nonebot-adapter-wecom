# NoneBot Adapter WeCom

基于企业微信官方 Python SDK 的 NoneBot2 适配器，用于接入企业微信智能机器人 API 模式的 WebSocket 长连接。

## 安装

```bash
uv add "nonebot-adapter-wecom @ git+https://github.com/cqunews/nonebot-adapter-wecom.git"
```

## 配置

在企业微信创建 API 模式的智能机器人，选择「使用长连接」，取得 Bot ID 和 Secret。在 NoneBot 项目的环境配置中加入：

```dotenv
WECOM_AIBOT_BOTS='[{"bot_id":"你的 Bot ID","secret":"你的 Secret"}]'
```

可配置多个机器人，每个 Bot ID 必须唯一。每个机器人还可设置 `reconnect_interval`、`heartbeat_interval` 和 `request_timeout`，单位均为毫秒。长连接由 SDK 管理，无需公网回调地址或 NoneBot WebSocket 驱动。

## 快速开始

```python
import nonebot
from nonebot.adapters.wecom import Adapter

nonebot.init(driver="~none")
nonebot.get_driver().register_adapter(Adapter)
nonebot.load_builtin_plugin("echo")

if __name__ == "__main__":
    nonebot.run()
```

默认命令前缀为 `/`。在私聊发送 `/echo 你好`，在群聊中先 @ 机器人再输入命令。企业微信话题发来的 `channel` 文本回调会移除开头的 @ 名称，便于内置 Echo 匹配，回复通过原始回调帧发送。在原话题内显示回复仍待客户端实测。

## 消息能力

| 功能 | 接口 |
| --- | --- |
| 接收文本、图片、图文混合、语音识别文本和文件 | `MessageEvent.get_message()` |
| 回复文本、Markdown 或模板卡片 | `Bot.send(event, message)` |
| 流式回复 | `Bot.reply_stream(event, content, stream_id=..., finish=...)` |
| 主动发送消息到会话 | `Bot.send_to(chatid, message)` |
| 下载并解密媒体 | `Bot.call_api("download_file", url=..., aes_key=...)` |

流式更新使用同一个 `stream_id` 并传入累计的完整文本。SDK负责认证、心跳、重连和回执。

## 开发

```bash
uv run python -m unittest discover -s tests
uv build
```
