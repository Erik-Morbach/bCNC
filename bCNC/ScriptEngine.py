import pathlib
import logging
from tkinter import Variable
from CNC import CNC
import Utils

logScript = logging.getLogger("Script")
logScript.setLevel(logging.INFO)

REFERENCE_PERIOD = Utils.getFloat("Connection", "write_poll", 0.01)

class ScriptEngine:
    def __init__(self, app) -> None:
        self.app = app

        self.scripts = {}
        self.loadScripts()

    def loadScripts(self):
        entries = pathlib.Path('scripts/')
        for file in entries.iterdir():
            with open('scripts/' + file.name) as fileObj:
                logScript.info("Script {} loaded".format(file.name.upper()))
                name = file.name[:file.name.find('.')].upper()
                self.scripts[name] = "\n".join(fileObj.readlines())

    def find(self, name):
        name = name.upper()
        #print("Finding {}".format(name))
        return name in self.scripts.keys()

    def _setBindings(self, local, globa):
        local["execute"] = self.execCommand
        local["code"] = self.code
        local["wait"] = self.wait
        local["sleep"] = self.sleep
        local["get"] = self.get
        local["set"] = self.set
        local["exist"] = self.exist

    def execute(self, name, local, globa):
        name = name.upper()
        #print("Executing {}".format(name))
        self._setBindings(local, globa)
        exec(self.scripts[name], local, globa)
    
    def execCommand(self, code):
        self.app.executeCommand(code)
    
    def code(self, gcode):
        self.app.sendGCode(gcode)

    def wait(self):
        self.app.sendGCode((4,))

    def sleep(self):
        self.app.sendGCode((8,0.1//REFERENCE_PERIOD))

    def exist(self, name):
        return name in CNC.vars.keys()

    def set(self, name, value):
        if self.exist(name) and isinstance(CNC.vars[name], Variable):
            CNC.vars[name].set(value)
            return
        CNC.vars[name] = value

    def get(self, name):
        if not self.exist(name): return 0
        if isinstance(CNC.vars[name], Variable): return CNC.vars[name].get()
        return CNC.vars[name]


