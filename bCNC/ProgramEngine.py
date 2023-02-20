from CNC import BEGIN_REPEAT_M30, END_REPEAT_M30

class ProgramEngine:
    def __init__(self, app) -> None:
        self.app = app
        self.reset()

    def reset(self):
        self.lineIndex = 0
        self.nextSend = None

    def isActive(self):
        return self.app.running

    def sendNext(self, cmd):
        self.nextSend = cmd

    def getNextCommand(self):
        if self.nextSend is not None:
            cmd = self.nextSend
            self.nextSend = None
            return cmd
        if self.lineIndex >= len(self.app.compiledProgram):
            return (BEGIN_REPEAT_M30,)
        cmd = self.app.compiledProgram[self.lineIndex]
        self.lineIndex+=1
        return cmd
