from CNC import BEGIN_REPEAT_M30, END_REPEAT_M30
import lib.Deque

class ProgramEngine:
    def __init__(self, app) -> None:
        self.app = app
        self.deque = lib.Deque.Deque()
        self.reset()

    def reset(self):
        self.lineIndex = 0
        self.nextSend = None
        self.deque.clear()

    def isActive(self):
        return self.app.running

    def appendLeft(self, cmd):
        self.deque.appendleft(cmd)

    def getNextCommand(self):
        if len(self.deque) > 0:
            return self.deque.popleft()
        if self.lineIndex >= len(self.app.compiledProgram):
            return (BEGIN_REPEAT_M30,)
        cmd = self.app.compiledProgram[self.lineIndex]
        self.lineIndex+=1
        return cmd
