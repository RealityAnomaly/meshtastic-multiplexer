
import logging

import base64
import cryptography
import cryptography.hazmat.primitives.ciphers
import cryptography.hazmat.primitives.ciphers.algorithms
import cryptography.hazmat.primitives.ciphers.modes
import cryptography.hazmat.backends
import meshtastic
import meshtastic.protobuf

from typing import Optional

logger = logging.getLogger('meshmtx:utils')


DEFAULT_FIRMWARE_KEY = "2"
DEFAULT_CRYPTO_KEY = 'AQ=='
DEFAULT_MAX_DISTANCE = 80000 # 80 km radius


class CryptoUtilities():
  @staticmethod
  def expand_key(key: str) -> str:
    if key == "AQ==":
      key = "1PG7OiApB1nwvP+rz05pAQ=="

    padded_key = key.ljust(len(key) + ((4 - (len(key) % 4)) % 4), '=')
    return padded_key.replace('-', '+').replace('_', '/')

class PacketUtilities():
  @staticmethod
  def node_to_user_id(id: str) -> int:
    return int(id, 16)
  
  @staticmethod
  def user_to_node_id(id: int) -> str:
    return f'{id:x}'

  @staticmethod
  def decode_envelope(payload: bytes) -> Optional[meshtastic.mqtt_pb2.ServiceEnvelope]:
    envelope = meshtastic.mqtt_pb2.ServiceEnvelope()
    try:
      envelope.ParseFromString(payload)
    except Exception as e:
      #logger.error(f"ServiceEnvelope: {str(e)}")
      return None
    
    if len(payload) > meshtastic.mesh_pb2.Constants.DATA_PAYLOAD_LEN:
      #logger.warn('Message too long: ' + str(len(payload)) + ' bytes long, skipping.')
      return None
    
    return envelope
  
  @staticmethod
  def decode_packet(packet, key = DEFAULT_CRYPTO_KEY) -> Optional[meshtastic.mesh_pb2.MeshPacket]:
    if packet.HasField("encrypted") and not packet.HasField("decoded"):
      if not PacketUtilities._decode_encrypted_packet(packet, key):
        return None
    return packet
  
  @staticmethod
  def topic_to_node_id(topic: str) -> Optional[str]:
    topic_split = topic.split('/')[-1]
    if not topic_split.startswith('!'):
      return None
    return topic_split.strip('!')

  @staticmethod
  def _decode_encrypted_packet(mp, key) -> bool:
    """Decrypt a meshtastic message."""

    key = CryptoUtilities.expand_key(key)

    try:
      # Convert key to bytes
      key_bytes = base64.b64decode(key.encode('ascii'))

      nonce_packet_id = getattr(mp, "id").to_bytes(8, "little")
      nonce_from_node = getattr(mp, "from").to_bytes(8, "little")

      # Put both parts into a single byte array.
      nonce = nonce_packet_id + nonce_from_node

      cipher = cryptography.hazmat.primitives.ciphers.Cipher(
        cryptography.hazmat.primitives.ciphers.algorithms.AES(key_bytes),
        cryptography.hazmat.primitives.ciphers.modes.CTR(nonce), backend=cryptography.hazmat.backends.default_backend()
      )
      decryptor = cipher.decryptor()
      decrypted_bytes = decryptor.update(getattr(mp, "encrypted")) + decryptor.finalize()

      data = meshtastic.mesh_pb2.Data()
      data.ParseFromString(decrypted_bytes)
      mp.decoded.CopyFrom(data)

    except Exception as e:
      #logger.debug(f'Failed to decrypt packet: {e}\n{mp}')
      return False

    return True
