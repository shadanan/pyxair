import asyncio
import logging
from datetime import datetime, timedelta

from .client import XAir

logger = logging.getLogger(__name__)


class XAirTask:
    def __init__(self, xinfo, connect=False):
        self._xinfo = xinfo
        self._xair = None
        self._task = None
        self.refresh()
        if connect:
            self.connect()

    def get_xair(self):
        return self._xair

    def refresh(self):
        self._seen = datetime.now()

    def is_stale(self, timeout=30):
        return datetime.now() - self._seen > timedelta(seconds=timeout)

    def connect(self):
        self._xair = XAir(self._xinfo)
        self._task = asyncio.create_task(self._xair.start())

    def cancel(self):
        if self._task:
            self._task.cancel()
        return self._task
