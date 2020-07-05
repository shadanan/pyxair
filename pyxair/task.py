import asyncio
import logging
from datetime import datetime, timedelta

from .client import XAir

logger = logging.getLogger(__name__)


class XAirTask:
    def __init__(self, xinfo, connect=False, meters=[]):
        self._xinfo = xinfo
        self._xair = XAir(self._xinfo)
        self._task = asyncio.create_task(self._xair.start())
        if connect:
            self._xair.enable_remote()
        for meter in meters:
            self._xair.enable_meter(meter)

    def get_xair(self):
        return self._xair

    def is_stale(self, timeout=10):
        return self._xair.is_stale(timeout)

    def cancel(self):
        self._task.cancel()
        return self._task
