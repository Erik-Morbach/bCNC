from types import CodeType
import queue


class Macro:
    def __init__(self, name) -> None:
        self.name = name
        self.mCode = Macro.getMCode(self.name)
        self.source = Macro.getSource(self.name)
        self.compiled = Macro.compileSource(self.source)

    @staticmethod
    def getSource(name) -> str:
        source = ""
        with open('macros/'+name) as file:
            source = "".join(file.readlines())
        return source

    @staticmethod
    def compileSource(source) -> CodeType:
        return compile(source, "", "exec")

    @staticmethod
    def getMCode(gcode:str) -> int:
        gcode = gcode.upper()
        index = gcode.find('M')
        if index == -1: return -1
        mcode = 0
        index += 1
        while gcode[index].isdigit():
            mcode = mcode*10 + int(gcode[index])
            index += 1
        return mcode


class Executor:
    def __init__(self, macro, CNCRef):
        self.CNC = CNCRef
        self.macro = macro
        self.queue = queue.Queue()
    def getQueue(self):
        return self.queue

    def execute(self, loca, globa):
        loca["code"] = self.code
        loca["wait"] = self.wait
        loca["get"] = self.get
        exec(self.macro.compiled, loca, globa)

    def code(self, gcode):
        if isinstance(gcode, str):
            gcode += '\n'
        self.queue.put(gcode)

    def get(self, name):
        return self.CNC.vars[name]

    def wait(self):
        self.queue.put((4,))
