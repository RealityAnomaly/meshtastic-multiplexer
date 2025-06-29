import paho.mqtt.client as mqtt
from sqlalchemy.orm import Session, sessionmaker
from typing import TYPE_CHECKING

from meshmtx.config import Config
from meshmtx.geocoder import NodeGeocoder
from meshmtx.mqtt.base import MQTTThreadBase
from meshmtx.utils import PacketUtilities, DEFAULT_FIRMWARE_KEY, DEFAULT_MAX_DISTANCE

if TYPE_CHECKING:
  from meshmtx.multiplexer import Multiplexer


class RemoteMQTTThread(MQTTThreadBase):
  _client: mqtt.Client

  def __init__(self, config: Config, storage: sessionmaker, geocoder: NodeGeocoder, multiplexer: 'Multiplexer'):
    MQTTThreadBase.__init__(self, 'remote', config, storage, geocoder, multiplexer)
  
  def on_connect(self, client, userdata, flags, reason_code, properties):
    if reason_code.value != mqtt.CONNACK_ACCEPTED:
      self._logger.error(f'Failed to connect to MQTT server with reason \"{reason_code}\".')
      return

    self._logger.info(f'Connected to MQTT server')
    for topic in self._mqtt_config.get('subscriptions', []):
      self._client.subscribe(topic)

    # for topic in self._config['imports']:
    #   topic_name = f'msh/{topic["region"]}/{DEFAULT_FIRMWARE_KEY}/e/{topic["remote"]}/#'
    #   self._client.subscribe(topic_name)
  
  def on_message(self, client, userdata, msg):
    # i.e. msh/EU_868/2/e/LongFast/!e2e52528
    # node_id = PacketUtilities.topic_to_node_id(msg.topic)
    # if not node_id:
    #   return
    envelope = PacketUtilities.decode_envelope(msg.payload)
    if not envelope:
      return
    
    # attempt to decrypt the packet and process it as telemetry using the default crypto key
    packet = PacketUtilities.decode_packet(envelope.packet)
    if packet and hasattr(envelope.packet, "from"):
      node_id = getattr(envelope.packet, "from")
      self.handle_telemetry_packet(node_id, packet)

      remote_entry = self._geocoder.get_node(node_id)
      if not remote_entry:
        return

      # forward the message to the right client multiplexer queue (if it exists)
      for client in self._config['clients']:
        id = PacketUtilities.node_to_user_id(client['id'])
        entry = self._geocoder.get_node(id)
        if not entry:
          continue

        # see if the target node is close enough to our node
        max_distance = client.get('max_distance', DEFAULT_MAX_DISTANCE)
        if not entry.is_within_distance_from(remote_entry, max_distance):
          continue

        # strip off the region prefix, then actually publish the message
        topic_suffix = '/'.join(msg.topic.split('/')[2:])
        self._multiplexer.local.publish_client(client['id'], msg.payload, topic_suffix)
