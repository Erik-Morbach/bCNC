import threading
import traceback

class ThreadVar:
    def __init__(self, val):
        self.val = val
        self.mtx = threading.Lock()

    def lock(self):
        if not self.mtx.acquire(blocking=True, timeout=5):
            a = 15/0

    def unlock(self):
        self.mtx.release()

    @property
    def value(self):
        self.lock()
        response = self.val
        self.unlock()
        return response

    @value.setter
    def value(self, val):
        self.lock()
        self.val = val
        self.unlock()

    def assign(self, func):
        self.lock()
        self.val = func(self.val)
        self.unlock()
        return self.val

    def execute(self, func):
        self.lock()
        value = func(self.val)
        self.unlock()
        return value


