import re
from typing import Any

from nonebot.adapters import Event as BaseEvent
from pydantic import Field

from .message import Message


class Event(BaseEvent):
    frame: dict[str, Any] = Field(repr=False)
    self_id: str

    @property
    def body(self) -> dict[str, Any]:
        return self.frame.get('body', {})

    def get_type(self) -> str:
        return 'notice'

    def get_event_name(self) -> str:
        return 'notice.' + self.body.get('event', {}).get('eventtype', 'unknown')

    def get_event_description(self) -> str:
        # 不将临时媒体 URL、aeskey 或完整回调写入日志。
        return f'{self.get_event_name()} from {self.body.get("from", {}).get("userid", "unknown")}'

    def get_user_id(self) -> str:
        userid = self.body.get('from', {}).get('userid')
        if not userid:
            raise ValueError('此事件没有用户 ID')
        return userid

    def get_session_id(self) -> str:
        if self.body.get('chattype') == 'group':
            return f'group_{self.body["chatid"]}_{self.get_user_id()}'
        return f'private_{self.get_user_id()}'

    def get_message(self) -> Message:
        raise ValueError('通知事件不包含消息')

    def is_tome(self) -> bool:
        # 智能机器人收到的群消息由平台在被 @ 时下发。
        return True


class MessageEvent(Event):
    def get_type(self) -> str:
        return 'message'

    def get_event_name(self) -> str:
        scope = 'group' if self.body.get('chattype') == 'group' else 'private'
        return f'message.{scope}.{self.body.get("msgtype", "unknown")}'

    def get_message(self) -> Message:
        # 缓存同一对象，使 NoneBot 的命令前缀处理能够更新消息。
        if '_message' not in self.__dict__:
            body = self.body
            message = Message.from_body(body)
            if (body.get('chattype') == 'group'
                    and body.get('msgtype') == 'text'
                    and (body.get('compat_info') or {}).get('source') == 'channel'):
                # 话题文本回调会保留开头的 @机器人名称。
                text = message[0].data['text']
                message[0].data['text'] = re.sub(r'^\s*@[^\s@]+\s+', '', text, count=1)
            self.__dict__['_message'] = message
        return self.__dict__['_message']
