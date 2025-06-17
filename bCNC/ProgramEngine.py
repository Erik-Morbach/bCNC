from CNC import BEGIN_REPEAT_M30, END_REPEAT_M30
import lib.Deque

class ProgramEngine:
    def __init__(self, app) -> None:
        self.app = app
        self.priorityDeque = lib.Deque.Deque()
        self.reset()

    def reset(self):
        self.lineIndex = 0
        self.nextSend = None
        self.priorityDeque.clear()

    def isActive(self):
        return self.app.running.value

    def appendLeft(self, cmd):
        self.priorityDeque.appendleft(cmd)

    # Return commands on the deque,
    # if empty, return next program line
    def getNextCommand(self):
        if len(self.priorityDeque) > 0:
            return self.priorityDeque.popleft()
        self.app.compiledProgram.lock()
        if self.lineIndex >= len(self.app.compiledProgram.val):
            self.app.compiledProgram.unlock()
            return (BEGIN_REPEAT_M30,)
        cmd = self.app.compiledProgram.val[self.lineIndex]
        self.app.compiledProgram.unlock()
        self.lineIndex+=1
        return cmd
