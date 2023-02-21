import collections
import threading


class Deque(collections.deque):
    def __init__(self):
        collections.deque.__init__(self)
        self.lock = threading.Lock()

    def appendleft(self, __x) -> None:
        self.lock.acquire(blocking=True)
        super().appendleft(__x)
        self.lock.release()

    def append(self, __x) -> None:
        self.lock.acquire(blocking=True)
        super().append(__x)
        self.lock.release()

    def pop(self):
        self.lock.acquire(blocking=True)
        data = super().pop()
        self.lock.release()
        return data

    def popleft(self):
        self.lock.acquire(blocking=True)
        data = super().popleft()
        self.lock.release()
        return data

    def rotate(self, __n: int = ...) -> None:
        self.lock.acquire(blocking=True)
        super().rotate(__n)
        self.lock.release()

    def __len__(self) -> int:
        self.lock.acquire(blocking=True)
        size = super().__len__()
        self.lock.release()
        return size

    def clear(self) -> None:
        self.lock.acquire(blocking=True)
        super().clear()
        self.lock.release()


