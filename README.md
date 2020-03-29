# pyxair

Python library for interacting with Behringer XAir devices.

## Usage

### Connect to XAir device:

```python
x_air = pyxair.auto_connect()
```

### Get & Set

After connecting to the XAir device, the XAir class will be operating in "immediate" mode. In this mode, calling `get` and `set` will always immediately send events to the XAir device.

Here's an example using the `get` coroutine to retrieve the status. This is achieved by sending an OSC message to the `/status` address:

```python
await x_air.get("/status")
```

Response:

```python
OscMessage(address='/status', arguments=['active', '192.168.86.128', 'XR18-5E-91-5A'])
```

This is am example using the `get` coroutine to retrieve the main L/R mix:

```python
await x_air.get("/lr/mix/on")
```

Response:

```python
OscMessage(address='/lr/mix/on', arguments=[0])
```

We can use the `set` coroutine to apply changes to the XAir device. In this example, we unmute the main L/R channel:

```python
await x_air.set("/lr/mix/on", [1])
```

If we now send a `get` request to the main L/R mix, we see that it is unmuted:

```python
await x_air.get("/lr/mix/on")
```

Response:

```python
OscMessage(address='/lr/mix/on', arguments=[1])
```

### Subscribe to Updates

After calling the `subscribe()` coroutine, the XAir device switches from "immediate" mode to "deferred" mode. In this mode, we subscribe to events from the XAir device. As update events arrive, they will be saved to a cache.

The behavior of the `get` coroutine will now return values from the cache instead of requesting updates directly from the XAir device. If the required OSC address is not in the cache, then `get` will request an update from the XAir device.

```python
subscription = asyncio.create_task(x_air.subscribe())
```

After subscribing, `x_air.subscribed` will be set to `True`. In this example, the XAir `cache` attribute currently looks like this:

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

Using `get` while in deferred mode on an OSC address not in the cache will fetch the value from the XAir device and update the cache:

```python
await x_air.get('/lr/mix/fader')
```

Now, the cache will look like this:

```python
{
    '/status': OscMessage(address='/status', arguments=['active', '192.168.86.128', 'XR18-5E-91-5A']),
    '/lr/mix/on': OscMessage(address='/lr/mix/on', arguments=[1]),
    '/lr/mix/fader': OscMessage(address='/lr/mix/fader', arguments=[0.5747800469398499])}
```

We can cancel the subscription by calling `cancel()` on the task returned from `subscribe()`:

```python
subscription.cancel()
```

Cancelling the subscription causes `x_air.subscribed` to be `False`.
