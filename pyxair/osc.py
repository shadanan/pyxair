import pythonosc.osc_message
import pythonosc.osc_message_builder
from collections import defaultdict, namedtuple


OscMessage = namedtuple("OscMessage", ["address", "arguments"])
XInfo = namedtuple("XInfo", ["ip", "port", "name", "model", "version"])


def encode(osc_message: OscMessage) -> bytes:
    builder = pythonosc.osc_message_builder.OscMessageBuilder(osc_message.address)
    for arg in osc_message.arguments:
        builder.add_arg(arg)
    return builder.build().dgram


def decode(dgram: bytes) -> OscMessage:
    message = pythonosc.osc_message.OscMessage(dgram)
    return OscMessage(message.address, message.params)
