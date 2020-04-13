# pyxair

Python library for interacting with Behringer XAir devices.

## Usage

### Detect XAir Devices

```python
xinfo = pyxair.auto_detect()
```

### Create an XAir Client

`XAirPubSub` subscribes to events from an XAir device and then distributes the messages to subscribed clients.

`XAirClient` is a client that subscribes to events from `XAirPubSub` and caches the messages.

```python
pubsub = pyxair.XAirPubSub(xinfo)
asyncio.create_task(pubsub.monitor())
xair = pyxair.XAirCacheClient(pubsub)
```

### Get & Set

Here's an example using the `get` coroutine to retrieve the status. This is achieved by sending an OSC message to the `/status` address:

```python
await xair.get("/status")
```

Response:

```python
OscMessage(address='/status', arguments=['active', '192.168.86.128', 'XR18-5E-91-5A'])
```

This is am example using the `get` coroutine to retrieve the main L/R mix:

```python
await xair.get("/lr/mix/on")
```

Response:

```python
OscMessage(address='/lr/mix/on', arguments=[0])
```

We can use the `set` coroutine to apply changes to the XAir device. In this example, we unmute the main L/R channel:

```python
await xair.set("/lr/mix/on", [1])
```

If we now send a `get` request to the main L/R mix, we see that it is unmuted:

```python
await xair.get("/lr/mix/on")
```

Response:

```python
OscMessage(address='/lr/mix/on', arguments=[1])
```

### Subscription Updates

In this example, the XAirCacheClient `cache` attribute currently looks like this:

```python
{
    '/status': OscMessage(address='/status', arguments=['active', '192.168.86.128', 'XR18-5E-91-5A']),
    '/lr/mix/on': OscMessage(address='/lr/mix/on', arguments=[0])
}
```

If you unmute the main L/R channel using X-AIR-Edit, or some other client, and then observe the `cache` attribute again, it will look like this:

```python
{
    '/status': OscMessage(address='/status', arguments=['active', '192.168.86.128', 'XR18-5E-91-5A']),
    '/lr/mix/on': OscMessage(address='/lr/mix/on', arguments=[1])
}
```

Using `get` on an OSC address not in the cache will fetch the value from the XAir device and update the cache:

```python
await xair.get('/lr/mix/fader')
```

Now, the cache will look like this:

```python
{
    '/status': OscMessage(address='/status', arguments=['active', '192.168.86.128', 'XR18-5E-91-5A']),
    '/lr/mix/on': OscMessage(address='/lr/mix/on', arguments=[1]),
    '/lr/mix/fader': OscMessage(address='/lr/mix/fader', arguments=[0.5747800469398499])}
```
