"""转换层单元测试：使用真实 NoneBot2，SDK 通过明确的测试替身隔离网络。"""
import asyncio
import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

# SDK 无需安装即可验证转换层；不属于真实 SDK / 企业微信集成测试。
fake_sdk = types.ModuleType('aibot')
fake_sdk.WSClient = object
fake_sdk.WSClientOptions = lambda **kwargs: SimpleNamespace(**kwargs)
sdk_patch = patch.dict(sys.modules, {'aibot': fake_sdk})
sdk_patch.start()


def tearDownModule():
    sdk_patch.stop()


from nonebot.adapters.wecom import Adapter, Bot, Event, Message, MessageEvent, MessageSegment
from nonebot.adapters.wecom.config import Config
from nonebot.config import Config as NBConfig
from nonebot.exception import ApiNotAvailable


def frame(kind='text', group=False):
    return {'headers': {'req_id': 'request-1'}, 'body': {
        'msgid': 'message-1', 'msgtype': kind,
        'from': {'userid': 'user-1'},
        'chattype': 'group' if group else 'single', 'chatid': 'chat-1',
        'text': {'content': '/ping'},
        'event': {'eventtype': 'enter_chat'},
    }}


class Driver:
    config = NBConfig(wecom_aibot_bots=[{'bot_id': 'bot-1', 'secret': 'test-secret'}])

    def on_startup(self, hook):
        self.startup = hook

    def on_shutdown(self, hook):
        self.shutdown = hook

    def _bot_connect(self, bot):
        pass

    def _bot_disconnect(self, bot):
        pass


class SDK:
    def __init__(self, options):
        self.options = options
        self.handlers = {}
        self.connect = AsyncMock()
        self.reply_stream = AsyncMock(return_value={'errcode': 0})
        self.send_message = AsyncMock(return_value={'errcode': 0})
        self.reply_welcome = AsyncMock(return_value={'errcode': 0})
        self.reply_template_card = AsyncMock(return_value={'errcode': 0})
        self.disconnected = False

    def on(self, name, handler):
        self.handlers[name] = handler

    def disconnect(self):
        self.disconnected = True


class ConversionTests(unittest.TestCase):
    def test_message(self):
        message = Message('你好') + MessageSegment.markdown('**世界**')
        self.assertEqual(message.outbound()['markdown']['content'], '你好**世界**')

    def test_mixed(self):
        msg = Message.from_body({'msgtype': 'mixed', 'mixed': {'msg_item': [
            {'msgtype': 'text', 'text': {'content': '图片'}},
            {'msgtype': 'image', 'image': {'url': 'private', 'aeskey': 'key'}},
        ]}})
        self.assertEqual(msg.extract_plain_text(), '图片')
        self.assertEqual(msg[1].data['aeskey'], 'key')
        with self.assertRaises(ValueError):
            msg.outbound()

    def test_events(self):
        event = MessageEvent(frame=frame(group=True), self_id='bot-1')
        self.assertEqual(event.get_session_id(), 'group_chat-1_user-1')
        self.assertEqual(event.get_event_name(), 'message.group.text')
        self.assertIs(event.get_message(), event.get_message())
        self.assertEqual(event.get_plaintext(), '/ping')
        self.assertNotIn('aeskey', event.get_log_string())
        event.get_message().clear()
        self.assertEqual(event.get_plaintext(), '')
        self.assertEqual(MessageEvent(frame=frame(), self_id='bot-1').get_session_id(), 'private_user-1')

    def test_config_validation(self):
        with self.assertRaises(ValueError):
            Config(wecom_aibot_bots=[{'bot_id': 'b', 'secret': ''}])
        with self.assertRaises(ValueError):
            Config(wecom_aibot_bots=[{'bot_id': 'b', 'secret': 's'}] * 2)
        self.assertNotIn('test-secret', repr(
            Config(wecom_aibot_bots=[{'bot_id': 'b', 'secret': 'test-secret'}])))

    def test_topic_text_removes_leading_mention_without_changing_frame(self):
        raw = frame(group=True)
        content = '@官方账号信息推送 /echo test @同事'
        raw['body']['text']['content'] = content
        raw['body']['compat_info'] = {'source': 'channel'}
        event = MessageEvent(frame=raw, self_id='bot-1')
        self.assertEqual(event.get_plaintext(), '/echo test @同事')
        self.assertEqual(event.body['text']['content'], content)

        raw['body'].pop('compat_info')
        ordinary_event = MessageEvent(frame=raw, self_id='bot-1')
        self.assertEqual(ordinary_event.get_plaintext(), content)

    def test_unsupported_and_empty(self):
        for msg in [Message(), Message(' '), MessageSegment.image('url')]:
            with self.assertRaises(ValueError):
                Message(msg).outbound()


class LifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.adapter = Adapter(Driver())
        with patch('nonebot.adapters.wecom.adapter.WSClient', SDK):
            await self.adapter._startup()
        await asyncio.sleep(0)
        self.client = self.adapter.clients['bot-1']
        self.client.handlers['authenticated']()
        self.bot = self.adapter.bots['bot-1']

    async def asyncTearDown(self):
        await self.adapter._shutdown()

    async def test_auth_disconnect_reauth(self):
        self.client.connect.assert_awaited_once()
        self.assertEqual(self.client.options.max_reconnect_attempts, -1)
        self.client.handlers['authenticated']()
        self.assertEqual(len(self.adapter.bots), 1)
        self.client.handlers['disconnected']('test')
        self.assertFalse(self.adapter.bots)
        self.client.handlers['authenticated']()
        self.assertIn('bot-1', self.adapter.bots)

    async def test_send_and_stream(self):
        event = MessageEvent(frame=frame(), self_id='bot-1')
        result = await self.bot.send(event, 'pong')
        self.client.reply_stream.assert_awaited_once_with(
            frame=event.frame, stream_id=result['stream_id'], content='pong', finish=True)
        await self.bot.reply_stream(event, '完整答案', stream_id='stream-1', finish=True)
        self.assertEqual(self.client.reply_stream.call_args.kwargs['stream_id'], 'stream-1')
        await self.bot.send_to('chat-1', '**主动消息**')
        self.client.send_message.assert_awaited_once()

    async def test_welcome_and_card(self):
        await self.bot.send(Event(frame=frame('event'), self_id='bot-1'), '欢迎')
        self.assertEqual(self.client.reply_welcome.call_args.kwargs['body']['msgtype'], 'text')
        card = {'card_type': 'text_notice', 'main_title': {'title': '通知'}}
        await self.bot.send(MessageEvent(frame=frame(), self_id='bot-1'), MessageSegment.template_card(card))
        self.client.reply_template_card.assert_awaited_once_with(frame=frame(), template_card=card)

    async def test_dispatch_once(self):
        with patch('nonebot.adapters.wecom.adapter.handle_event', new_callable=AsyncMock) as handler:
            self.client.handlers['message'](frame())
            await asyncio.sleep(0)
            handler.assert_awaited_once()
            self.assertIsInstance(handler.call_args.args[1], MessageEvent)
            await self.adapter._dispatch(self.bot, frame('event'))
            self.assertIsInstance(handler.call_args.args[1], Event)
        self.assertNotIn('message.text', self.client.handlers)

    async def test_shutdown_and_api_guard(self):
        with self.assertRaises(ApiNotAvailable):
            await self.bot.call_api('disconnect')
        await self.adapter._shutdown()
        self.assertTrue(self.client.disconnected)
        self.assertFalse(self.adapter.bots)
        self.assertFalse(self.adapter.tasks)
        with self.assertRaises(ApiNotAvailable):
            await self.bot.send_to('chat', 'test')
