from typing import Any

from nonebot.adapters import Message as BaseMessage
from nonebot.adapters import MessageSegment as BaseMessageSegment


class MessageSegment(BaseMessageSegment['Message']):
    @classmethod
    def get_message_class(cls):
        return Message

    def __str__(self) -> str:
        return self.data.get('text', '') if self.is_text() else f'[{self.type}]'

    def is_text(self) -> bool:
        return self.type in {'text', 'markdown'}

    @staticmethod
    def text(text: str):
        return MessageSegment('text', {'text': text})

    @staticmethod
    def markdown(text: str):
        return MessageSegment('markdown', {'text': text})

    @staticmethod
    def template_card(card: dict[str, Any]):
        return MessageSegment('template_card', {'template_card': card})

    @staticmethod
    def image(url: str, aeskey: str | None = None):
        return MessageSegment('image', {'url': url, 'aeskey': aeskey})


class Message(BaseMessage[MessageSegment]):
    @classmethod
    def get_segment_class(cls):
        return MessageSegment

    @staticmethod
    def _construct(msg: str):
        yield MessageSegment.text(msg)

    @classmethod
    def from_body(cls, body: dict[str, Any]):
        message = cls()
        kind = body.get('msgtype', '')
        items = body.get('mixed', {}).get('msg_item', []) if kind == 'mixed' else [body]
        for item in items:
            kind = item.get('msgtype', '')
            data = item.get(kind, {})
            if kind in {'text', 'voice'}:
                message.append(MessageSegment.text(data.get('content', '')))
            elif kind:
                message.append(MessageSegment(kind, dict(data)))
        return message

    def outbound(self) -> dict[str, Any]:
        if len(self) == 1 and self[0].type == 'template_card':
            return {'msgtype': 'template_card', **self[0].data}
        if not self or any(not segment.is_text() for segment in self):
            raise ValueError('发送仅支持非空文本/Markdown，或单个模板卡片；媒体段仅用于接收')
        content = str(self)
        if not content.strip():
            raise ValueError('消息内容不能为空')
        return {'msgtype': 'markdown', 'markdown': {'content': content}}
