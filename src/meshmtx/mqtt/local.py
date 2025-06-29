import paho.mqtt.client as mqtt
from sqlalchemy.orm import Session, sessionmaker
from typing import TYPE_CHECKING

from meshmtx.geocoder import NodeGeocoder
from meshmtx.mqtt.base import MQTTThreadBase
from meshmtx.config import Config
from meshmtx.utils import PacketUtilities

if TYPE_CHECKING:
  from meshmtx.multiplexer import Multiplexer


class LocalMQTTThread(MQTTThreadBase):
  _client: mqtt.Client

  def __init__(self, config: Config, storage: sessionmaker, geocoder: NodeGeocoder, multiplexer: 'Multiplexer'):
    MQTTThreadBase.__init__(self, 'local', config, storage, geocoder, multiplexer)

  def on_connect(self, client, userdata, flags, reason_code, properties):
    if reason_code.value != mqtt.CONNACK_ACCEPTED:
      self._logger.error(f'Failed to connect to MQTT server with reason \"{reason_code}\".')
      return

    self._logger.info(f'Connected to MQTT server')
    self._client.subscribe('msh/router/#')

  def on_message(self, client, userdata, msg):
    # node_id = PacketUtilities.topic_to_node_id(msg.topic)
    # if not node_id:
    #   return
    envelope = PacketUtilities.decode_envelope(msg.payload)
    if not envelope:
      return

    is_telemetry = False
    if envelope.channel_id == self._config['telemetry']['id']:
      decoded = PacketUtilities.decode_packet(envelope.packet, self._config['telemetry']['key'])
      if not decoded:
        return
      self.handle_telemetry_packet(getattr(envelope.packet, "from"), decoded)
      is_telemetry = True # telemetry channel is excluded from forwarding to remote

    # fan out packet to other multiplex queues on the local server
    if hasattr(envelope.packet, "from"):
      node_id = getattr(envelope.packet, "from")
      for client in self._config['clients']:
        id = PacketUtilities.node_to_user_id(client['id'])
        if id == node_id:
          continue
        self.publish_client(client['id'], msg.payload)
  
  def publish_client(self, id: str, payload, suffix = None):
    if suffix:
      suffix = '/' + suffix
    else:
      suffix = ''

    self.publish(f'msh/router/{id}{suffix}', payload)
