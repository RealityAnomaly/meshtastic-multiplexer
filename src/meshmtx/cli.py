import argparse
import yaml
import logging
import os
import signal

from meshmtx.config import Config
from meshmtx.multiplexer import Multiplexer
import meshmtx.storage

def main():
  parser = argparse.ArgumentParser(
    prog='meshtastic-multiplexer',
    formatter_class=argparse.RawDescriptionHelpFormatter,
    description='''
    (c) 2024 Alex XZ Cypher Zero

    Tool to forward messages between local and remote MQTT queues based on a mesh radio location.
    '''
  )

  parser.add_argument('-c', '--config', type=str, default='config.yaml', help='The config file to use')
  parser.add_argument('-s', '--state', type=str, default='state.db', help='Path to the state database')
  parser.add_argument('-v', '--verbose', action='store_true', default=bool(os.getenv('VERBOSE')), help='Enable debug output')
  args = parser.parse_args()

  with open(args.config, 'r') as f:
    config: Config = yaml.load(f, yaml.SafeLoader)
  
  log_level = logging.DEBUG if args.verbose else logging.INFO
  logging.basicConfig(level=log_level)
  
  storage = meshmtx.storage.get_engine(path=args.state)
  meshmtx.storage.Base.metadata.create_all(storage)

  multiplexer = Multiplexer(config, storage)

  signal.signal(signal.SIGINT, lambda sig, _frame: multiplexer.stop())
  signal.signal(signal.SIGTERM, lambda sig, _frame: multiplexer.stop())

  multiplexer.run()

if __name__ == "__main__":
  main()
