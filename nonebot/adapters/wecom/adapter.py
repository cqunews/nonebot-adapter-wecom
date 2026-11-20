import asyncio
import inspect
from typing import Any

from aibot import WSClient, WSClientOptions
from nonebot.adapters import Adapter as BaseAdapter
from nonebot.compat import model_dump, type_validate_python
from nonebot.exception import ApiNotAvailable
from nonebot.log import logger
from nonebot.message import handle_event

from .bot import Bot
from .config import Config
from .event import Event, MessageEvent


class Adapter(BaseAdapter):
    @classmethod
    def get_name(cls) -> str:
        return 'WeCom AI Bot'

    def __init__(self, driver, **kwargs):
        super().__init__(driver, **kwargs)
        self.adapter_config = type_validate_python(Config, model_dump(driver.config))
        self.clients: dict[str, WSClient] = {}
        self.tasks: set[asyncio.Task] = set()
        self.stopping = False
        driver.on_startup(self._startup)
        driver.on_shutdown(self._shutdown)

    def _spawn(self, coroutine):
        task = asyncio.create_task(coroutine)
        self.tasks.add(task)
        task.add_done_callback(self._done)
        return task

    def _done(self, task):
        self.tasks.discard(task)
        if not task.cancelled() and task.exception() is not None:
            # SDK 异常可能含认证数据，不输出原始异常。
            logger.error('WeCom AI Bot 后台任务失败：{}', type(task.exception()).__name__)

    def _bind(self, bot: Bot, client: WSClient):
        def authenticated():
            if not self.stopping and bot.self_id not in self.bots:
                self.bot_connect(bot)

        def disconnected(*_):
            if bot.self_id in self.bots:
                self.bot_disconnect(bot)

        def receive(frame):
            if not self.stopping and bot.self_id in self.bots:
                self._spawn(self._dispatch(bot, frame))

        client.on('authenticated', authenticated)
        client.on('disconnected', disconnected)
        # 只监听通用事件，避免与 message.text 等事件重复分发。
        client.on('message', receive)
        client.on('event', receive)
        client.on('error', lambda *_: logger.warning('WeCom AI Bot SDK 报告连接或协议错误'))

    async def _dispatch(self, bot: Bot, frame: dict[str, Any]):
        try:
            cls = Event if frame.get('body', {}).get('msgtype') == 'event' else MessageEvent
            await handle_event(bot, cls(frame=frame, self_id=bot.self_id))
        except Exception as exc:
            logger.error('WeCom AI Bot 事件处理失败：{}', type(exc).__name__)

    async def _startup(self):
        self.stopping = False
        for config in self.adapter_config.wecom_aibot_bots:
            client = WSClient(WSClientOptions(
                bot_id=config.bot_id, secret=config.secret.get_secret_value(),
                reconnect_interval=config.reconnect_interval,
                max_reconnect_attempts=-1,
                heartbeat_interval=config.heartbeat_interval,
                request_timeout=config.request_timeout,
            ))
            self.clients[config.bot_id] = client
            self._bind(Bot(self, config.bot_id), client)
            self._spawn(client.connect())

    async def _shutdown(self):
        self.stopping = True
        tasks = list(self.tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        for client in self.clients.values():
            try:
                result = client.disconnect()
                if inspect.isawaitable(result):
                    await result
            except Exception as exc:
                logger.warning('WeCom AI Bot 断开失败：{}', type(exc).__name__)
        for bot in list(self.bots.values()):
            self.bot_disconnect(bot)
        self.clients.clear()

    async def _call_api(self, bot: Bot, api: str, **data: Any):
        allowed = {
            'reply', 'reply_stream', 'reply_welcome', 'reply_template_card',
            'reply_stream_with_card', 'update_template_card', 'send_message', 'download_file',
        }
        if api not in allowed or bot.self_id not in self.bots:
            raise ApiNotAvailable(self.get_name())
        return await getattr(self.clients[bot.self_id], api)(**data)
