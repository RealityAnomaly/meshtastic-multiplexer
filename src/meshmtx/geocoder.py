import geocoder
import geopy.distance
import typing
import logging
import pycountry
import enum

logger = logging.getLogger('meshmtx:geocoder')

class NodePrecision(enum.IntEnum):
  COUNTRY = 1
  STATE = 2
  CITY = 3

class NodeEntry:
  id: int
  latitude: float
  longitude: float
  
  address: typing.Optional[str] = None
  city: typing.Optional[str] = None
  country: typing.Optional[str]
  country_iso3: typing.Optional[str] = None
  country_iso2: typing.Optional[str] = None
  neighborhood: typing.Optional[str] = None
  postal: typing.Optional[str] = None
  region: typing.Optional[str] = None
  state: typing.Optional[str] = None

  gis_dirty: bool = True

  def __init__(self, id: int, latitude: float, longitude: float):
    self.id = id
    self.latitude = latitude
    self.longitude = longitude
  
  def is_within_distance_from(self, other: "NodeEntry", max_distance_metres: int) -> bool:
    metres = geopy.distance.geodesic((self.latitude, self.longitude), (other.latitude, other.longitude)).meters
    if metres > max_distance_metres:
      return False
    return True

  def get_topic(self, precision: NodePrecision = NodePrecision.CITY) -> typing.Optional[str]:
    """
    Returns the MQTT topic path for the specific locational precision. None if the requested precision is unavailable.
    """
    if precision >= NodePrecision.COUNTRY:
      iso_code = self.country_iso2
      if not iso_code:
        iso_code = self.country_iso3
      if not iso_code:
        return None
      if precision == NodePrecision.COUNTRY:
        return iso_code
    
    path: typing.List[str] = []
    if precision >= NodePrecision.STATE:
      if not self.state:
        return None
      path.append(self.state)
      if precision == NodePrecision.STATE:
        return '/'.join(path)
    
    if precision >= NodePrecision.CITY:
      if not self.city:
        return None
      path.append(self.city.lower())
      if precision == NodePrecision.CITY:
        return '/'.join(path)
    
    return '/'.join(path)

  def get_most_precise_topic(self, precision: NodePrecision) -> typing.Optional[str]:
    """
    Returns the most precise MQTT topic path for the specified maximum precision. Can return None if no geocoded data is available.
    """
    curr = precision
    while True:
      if curr < NodePrecision.COUNTRY:
        return None
      topic = self.get_topic(curr)
      if topic:
        return topic
      curr = NodePrecision(curr - 1)

class NodeGeocoder:
  _entries: typing.Dict[int, NodeEntry] = {}
  _iso3_to_country: typing.Dict[str, str] = {}

  def __init__(self):
    for country in pycountry.countries:
      self._iso3_to_country[country.alpha_3] = country # type: ignore

  def get_node(self, id: int, needs_gis = False) -> typing.Optional[NodeEntry]:
    entry = self._entries.get(id)
    if not entry:
      return None
    if needs_gis and entry.gis_dirty:
      self.update_node_gis(id, entry)

    return entry

  def maybe_update_node(self, id: int, latitude: float, longitude: float):
    entry = self._entries.get(id)
    if not entry:
      entry = NodeEntry(id, latitude, longitude)

    if entry.latitude != latitude or entry.longitude != longitude:
      entry.latitude = latitude
      entry.longitude = longitude
      entry.gis_dirty = True
    
    self._entries[id] = entry
  
  def update_node_gis(self, id: int, entry: NodeEntry):
    result = None
    try:
      result = geocoder.reverse([entry.latitude, entry.longitude], 'arcgis')
    except Exception as e:
      logger.warning(f"failed to reverse geocode node {id} at lat={entry.latitude} long={entry.longitude}: {e}")
    if result is None or not result.ok:
      return
    
    country_iso3 = typing.cast(str, getattr(result, 'country', None))
    if not country_iso3:
      return None
    country_entry = self._iso3_to_country.get(country_iso3)
    if country_entry:
      entry.country = self._iso3_to_country.get(country_iso3).name # type: ignore
      entry.country_iso2 = self._iso3_to_country.get(country_iso3).alpha_2 # type: ignore

    entry.address = typing.cast(str, getattr(result, 'address', None))
    entry.city = typing.cast(str, getattr(result, 'city', None))
    entry.country_iso3 = country_iso3
    entry.neighborhood = typing.cast(str, getattr(result, 'neighborhood', None))
    entry.postal = typing.cast(str, getattr(result, 'postal', None))
    entry.region = typing.cast(str, getattr(result, 'region', None))
    entry.state = typing.cast(str, getattr(result, 'state', None))

    entry.gis_dirty = False
