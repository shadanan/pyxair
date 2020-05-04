from datetime import datetime
from typing import List, NamedTuple, Union

import pythonosc.osc_message
import pythonosc.osc_message_builder


class XInfo(NamedTuple):
    ip: str
    port: int
    name: str
    model: str
    version: str


class OscMessage(NamedTuple):
    address: str
    arguments: List[Union[int, float, str, bytes, datetime]]


def encode(osc_message: OscMessage) -> bytes:
    builder = pythonosc.osc_message_builder.OscMessageBuilder(osc_message.address)
    for arg in osc_message.arguments:
        builder.add_arg(arg)
    return builder.build().dgram


def decode(dgram: bytes) -> OscMessage:
    message = pythonosc.osc_message.OscMessage(dgram)
    return OscMessage(message.address, message.params)
