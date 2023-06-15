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
    def __init__(self, macro, app, CNCRef):
        self.CNC = CNCRef
        self.app = app
        self.macro = macro
        self.queue = queue.Queue()
    def getQueue(self):
        return self.queue

    def execute(self, loca, globa):
        loca["code"] = self.code
        loca["wait"] = self.wait
        loca["get"] = self.get
        loca["set"] = self.set
        loca["send"] = self.send
        exec(self.macro.compiled, loca, globa)

    def code(self, gcode):
        gcode = self.app.evaluate(gcode)
        nex = None
        if isinstance(gcode, str): gcode += "\n"
        elif isinstance(gcode, list): gcode += ['\n']
        else: nex = '\n'
        self.queue.put(gcode)
        if nex is not None: self.queue.put('\n')

    def send(self, code):
        self.queue.put(code)

    def set(self, name, value):
        self.CNC.vars[name] = value

    def get(self, name):
        return self.CNC.vars[name]

    def wait(self):
        self.queue.put((4,))
