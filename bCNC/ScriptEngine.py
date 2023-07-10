import pathlib
from tkinter import Variable
from CNC import CNC

class ScriptEngine:
    def __init__(self, app) -> None:
        self.app = app

        self.scripts = {}
        self.loadScripts()

    def loadScripts(self):
        entries = pathlib.Path('scripts/')
        for file in entries.iterdir():
            with open('scripts/' + file.name) as fileObj:
                print("Script {} loaded".format(file.name.upper()))
                name = file.name[:file.name.find('.')].upper()
                self.scripts[name] = "\n".join(fileObj.readlines())

    def find(self, name):
        name = name.upper()
        #print("Finding {}".format(name))
        for scriptNames in self.scripts.keys():
            if scriptNames == name: # TODO: bug, this do not deal with extensions
                return True

    def execute(self, name, local, globa):
        name = name.upper()
        #print("Executing {}".format(name))
        local["execute"] = self.execCommand
        local["code"] = self.code
        local["wait"] = self.wait
        local["sleep"] = self.sleep
        local["get"] = self.get
        local["set"] = self.set
        local["exist"] = self.exist
        exec(self.scripts[name], local, globa)

    def execCommand(self, code):
        self.app.executeCommand(code)

    def code(self, gcode):
        self.app.sendGCode(gcode)

    def sleep(self):
        self.app.sendGCode((8,200))

    def exist(self, name):
        return name in CNC.vars.keys()

    def set(self, name, value):
        if name in CNC.vars.keys() and isinstance(CNC.vars[name], Variable):
            CNC.vars[name].set(value)
            return

        CNC.vars[name] = value

    def get(self, name):
        if isinstance(CNC.vars[name], Variable):
            return CNC.vars[name].get()
        return CNC.vars[name]

    def wait(self):
        self.app.sendGCode((4,))
