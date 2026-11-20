"""基于 wecom-aibot-python-sdk 的 NoneBot2 长连接适配器。"""
from .adapter import Adapter
from .bot import Bot
from .event import Event, MessageEvent
from .message import Message, MessageSegment

__all__ = ['Adapter', 'Bot', 'Event', 'MessageEvent', 'Message', 'MessageSegment']
