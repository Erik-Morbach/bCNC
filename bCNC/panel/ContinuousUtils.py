import threading
import time


class ContinuousUtils:
    def __init__(self, period):
        self.period = period
        self.activeFn = {}
        self.periods = {}
        self.lastTime = {}
        self.mtx = threading.Lock()
        self.th = None

    def start(self):
        self.mtx.acquire()
        self.th = threading.Thread(target=self.task)
        self.th.start()

    def stop(self):
        self.mtx.release()
        self.th.join()
        self.th = None

    def task(self):
        while self.mtx.locked():
            time.sleep(self.period)
            self.callback()

    def registerMember(self, id, fn, period):
        self.activeFn[id] = fn
        self.periods[id] = period
        self.lastTime[id] = 0

    def removeMember(self, id):
        if id in self.activeFn:
            self.activeFn.pop(id)
        if id in self.periods:
            self.periods.pop(id)
        if id in self.lastTime:
            self.lastTime.pop(id)

    def execute(self, id, currentTime):
        self.lastTime[id] = currentTime
        shouldContinue = True
        try:
            response = self.activeFn[id]()
            if response is not None:
                shouldContinue = shouldContinue and bool(response)
        except Exception:
            return False
        return shouldContinue

    def callback(self):
        currentTimeMs = time.perf_counter_ns()/1000/1000
        listToDelete = []
        for id in self.activeFn.keys():
            if currentTimeMs - self.lastTime[id] >= self.periods[id]:
                if not self.execute(id, currentTimeMs):
                    listToDelete += [id]
        for id in listToDelete:
            self.removeMember(id)
