import typing


class ConfigClient(typing.TypedDict):
  id: str
  max_distance: int


class ConfigTelemetry(typing.TypedDict):
  id: str
  key: str


class ConfigQueueImport(typing.TypedDict):
  region: str
  remote: str
  local: str


class ConfigMQTT(typing.TypedDict):
  address: str
  port: int
  username: str
  password: str
  subscriptions: typing.List[str]


class ConfigMQTTDict(typing.TypedDict):
  local: ConfigMQTT
  remote: ConfigMQTT


class Config(typing.TypedDict):
  clients: typing.List[ConfigClient]
  telemetry: ConfigTelemetry
  imports: typing.List[ConfigQueueImport]
  mqtt: ConfigMQTTDict
