import logging
import typing

import sqlalchemy.engine
import sqlalchemy.orm

from meshmtx.config import Config
from meshmtx.geocoder import NodeGeocoder
from meshmtx.mqtt.local import LocalMQTTThread
from meshmtx.mqtt.remote import RemoteMQTTThread
from meshmtx.storage import NodeState

logger = logging.getLogger('meshmtx:multiplexer')


class Multiplexer:
  _config: Config
  _storage: sqlalchemy.engine.Engine
  _geocoder: NodeGeocoder

  local: LocalMQTTThread
  remote: RemoteMQTTThread

  def __init__(self, config: Config, storage: sqlalchemy.engine.Engine):
    self._config = config
    self._storage = storage
    self._geocoder = NodeGeocoder()
  
  def _load_nodes(self):
    with sqlalchemy.orm.Session(self._storage) as session:
      for node in session.query(NodeState):
        if node.latitude == None or node.longitude == None:
          continue
        self._geocoder.maybe_update_node(node.id, node.latitude, node.longitude)
  
  def run(self):
    self._load_nodes()

    session_factory = sqlalchemy.orm.sessionmaker(bind=self._storage)
    self.local = LocalMQTTThread(self._config, session_factory, self._geocoder, self)
    self.remote = RemoteMQTTThread(self._config, session_factory, self._geocoder, self)
    
    self.local.start()
    self.remote.start()

    self.local.join()
    self.remote.join()
  
  def stop(self):
    self.local.stop()
    self.remote.stop()
