import pathlib

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
        exec(self.scripts[name], local, globa)
