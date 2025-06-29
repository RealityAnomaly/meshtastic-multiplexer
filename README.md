Tool to forward messages between local and remote MQTT queues based on a mesh radio location. See config.example.yaml for an example configuration.

Basically, you can use it to publish and subscribe your devices only to region specific queues to avoid your device being spammed by all the messages from a country wide one. This didn't and up being that useful because not that many people actually make use of the local queues, but I decided to publish this repo in case the code is useful.

## Development

`pip install -e .`
