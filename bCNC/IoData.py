import threading
from ThreadVar import ThreadVar
import copy

class IoData:
    def __init__(self) -> None:
        self._sio_count = ThreadVar(0)
        self._sio_wait = ThreadVar(False)
        self._cline = ThreadVar([])
        self._sline = ThreadVar([])
        self.macrosRunning = ThreadVar(0)
        self._toSend = ThreadVar(None)
        self.processNode = ThreadVar(None)

    def deleteFirstLine(self):
        self._cline.execute(lambda c: c.pop(0) if c else None)
        value = self._sline.execute(lambda s: s.pop(0) if s else None)
        return value

    def clear(self):
        self._sio_wait.value = False # After clear you should wait until every motion
                              # is complete
        self._cline.execute(lambda c: c.clear())
        self._sline.execute(lambda s: s.clear())
        self.macrosRunning.value = 0
        self._toSend.value = None
        self.processNode.value = None

    @property
    def sio_count(self):
        return int(self._sio_count.value)

    @sio_count.setter
    def sio_count(self, value):
        self._sio_count.value = value

    def incrementSioCount(self):
        self._sio_count.assign(lambda x: x+1)

    def decrementSioCount(self):
        self._sio_count.assign(lambda x: max(0,x-1))

    @property
    def sio_wait(self):
        return self._sio_wait.value

    @sio_wait.setter
    def sio_wait(self, value):
        self._sio_wait.value = value

    @property
    def sumCline(self):
        return self._cline.execute(lambda x: sum(x))

    def addToLineBuffer(self, line):
        self._toSend.value = line
        self._cline.execute(lambda c: c.append(len(line.src)))
        self._sline.execute(lambda s: s.append(line.src))

    @property
    def toSend(self):
        return copy.deepcopy(self._toSend.value)

    @toSend.setter
    def toSend(self, value):
        self._toSend.value = value

