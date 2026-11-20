from typing import Any
from uuid import uuid4

from nonebot.adapters import Bot as BaseBot

from .event import Event, MessageEvent
from .message import Message, MessageSegment


class Bot(BaseBot):
    async def send(self, event: Event, message: str | Message | MessageSegment, **kwargs: Any):
        body = Message(message).outbound()
        if isinstance(event, MessageEvent):
            if body['msgtype'] == 'template_card':
                return await self.call_api('reply_template_card', frame=event.frame,
                                           template_card=body['template_card'])
            return await self.reply_stream(event, body['markdown']['content'], finish=True)
        if event.body.get('event', {}).get('eventtype') == 'enter_chat':
            if body['msgtype'] == 'markdown':
                body = {'msgtype': 'text', 'text': {'content': body['markdown']['content']}}
            return await self.call_api('reply_welcome', frame=event.frame, body=body)
        raise ValueError('此通知不支持 send，请使用主动发送或对应 SDK API')

    async def reply_stream(self, event: MessageEvent, content: str, *,
                           stream_id: str | None = None, finish: bool = False):
        """多次更新必须复用同一 stream_id，content 为累积完整内容。"""
        if finish and not content.strip():
            raise ValueError('流式结束内容不能为空')
        stream_id = stream_id or uuid4().hex
        result = await self.call_api('reply_stream', frame=event.frame,
                                    stream_id=stream_id, content=content, finish=finish)
        return {'stream_id': stream_id, 'result': result}

    async def send_to(self, chatid: str, message: str | Message | MessageSegment):
        return await self.call_api('send_message', chatid=chatid, body=Message(message).outbound())
