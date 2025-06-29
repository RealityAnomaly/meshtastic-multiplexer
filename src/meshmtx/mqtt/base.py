import threading
import logging
import time

import paho.mqtt.client as mqtt
import meshtastic
import meshtastic.protobuf

from datetime import datetime
import sqlalchemy
import sqlalchemy.orm
from sqlalchemy.orm import Session, sessionmaker

from typing import TYPE_CHECKING

from meshmtx.config import Config, ConfigMQTT
from meshmtx.geocoder import NodeGeocoder
from meshmtx.storage import NodeState

if TYPE_CHECKING:
  from meshmtx.multiplexer import Multiplexer


class MQTTThreadBase(threading.Thread):
  _key: str
  _config: Config
  _storage: Session
  _geocoder: NodeGeocoder
  _multiplexer: 'Multiplexer'

  _mutex = threading.Lock()
  _logger: logging.Logger
  _mqtt_config: ConfigMQTT

  def __init__(self, key: str, config: Config, storage: sessionmaker, geocoder: NodeGeocoder, multiplexer: 'Multiplexer'):
    threading.Thread.__init__(self, name=f'mqtt:{key}')
    self._key = key
    self._config = config
    self._storage = sqlalchemy.orm.scoped_session(storage)()
    self._geocoder = geocoder
    self._multiplexer = multiplexer

    self._logger = logging.getLogger(f'meshmtx:mqtt:{key}')
    self._mqtt_config = config['mqtt'][key]
  
  def on_connect(self, client, userdata, flags, reason_code, properties):
    if reason_code.value != mqtt.CONNACK_ACCEPTED:
      self._logger.error(f'Failed to connect to MQTT server with reason \"{reason_code}\".')
      return

    self._logger.info(f'Connected to MQTT server')
  
  def on_connect_fail(self, client, userdata):
    self._logger.error('Failed to connect to MQTT server, will retry')

  def on_message(self, client, userdata, msg):
    raise NotImplementedError()
  
  def run(self):
    self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2) # type: ignore
    self._client.on_connect = self.on_connect
    self._client.on_connect_fail = self.on_connect_fail
    self._client.on_message = self.on_message

    self._client.username_pw_set(self._mqtt_config['username'], self._mqtt_config['password'])
    self._client.connect_async(self._mqtt_config['address'], self._mqtt_config['port'])
    
    # handle TimeoutError, which for some reason isn't internally in paho-mqtt
    while True:
      try:
        self._client.loop_forever(retry_first_connection=True)
      except TimeoutError:
        self.on_connect_fail(None, None)
        time.sleep(10)
        continue
      break
  
  def stop(self):
    self._client.disconnect()
    self._storage.close()
  
  def publish(self, topic: str, payload):
    with self._mutex:
      self._client.publish(topic, payload)
  
  def handle_telemetry_packet(self, node_id: int, packet: meshtastic.mesh_pb2.MeshPacket):
    # is the client sending its location? if so, update the geocoded MQTT route

    if packet.decoded.portnum == meshtastic.portnums_pb2.POSITION_APP:
      position = meshtastic.mesh_pb2.Position()
      try:
        position.ParseFromString(packet.decoded.payload)
      except Exception:
        return

      # store the position
      self.try_store_position(node_id, position)
  
  def try_store_position(self, node_id: int, position: meshtastic.mesh_pb2.Position):
    # Must have latitude and longitude
    if position.latitude_i == 0 or position.longitude_i == 0:
      return
    
    # Integer to decimal position
    latitude = position.latitude_i * 1e-7
    longitude = position.longitude_i * 1e-7
    
    # Get the best timestamp
    timestamp = time.gmtime()
    if position.timestamp > 0:
      timestamp = time.gmtime(position.timestamp)
    if position.time > 0:
      timestamp = time.gmtime(position.time)
    timestamp = datetime.fromtimestamp(time.mktime(timestamp))

    # check for an existing record
    record = self._storage.scalar(sqlalchemy.select(NodeState).where(NodeState.id == node_id))
    
    updated = False
    if record:
      if timestamp > record.timestamp:
        record.timestamp = timestamp
        record.latitude = latitude
        record.longitude = longitude

        self._storage.commit()
        updated = True
    else:
      record = NodeState()
      record.id = node_id
      record.timestamp = timestamp
      record.latitude = latitude
      record.longitude = longitude

      self._storage.add(record)
      self._storage.commit()
      updated = True
    
    if updated:
      self._geocoder.maybe_update_node(node_id, latitude, longitude)
      self._logger.debug(f"updated position for node {node_id} to lat={latitude} long={longitude}")
