from pydantic import BaseModel, Field, SecretStr, validator


class BotConfig(BaseModel):
    bot_id: str = Field(min_length=1)
    secret: SecretStr
    reconnect_interval: int = Field(default=1000, gt=0)
    heartbeat_interval: int = Field(default=30000, gt=0)
    request_timeout: int = Field(default=10000, gt=0)

    @validator("secret")
    def check_secret(cls, value):
        if not value.get_secret_value():
            raise ValueError("secret 不能为空")
        return value


class Config(BaseModel):
    wecom_aibot_bots: list[BotConfig] = Field(default_factory=list)

    @validator("wecom_aibot_bots")
    def unique_ids(cls, value):
        ids = [bot.bot_id for bot in value]
        if len(ids) != len(set(ids)):
            raise ValueError("wecom_aibot_bots 中 bot_id 不可重复")
        return value
