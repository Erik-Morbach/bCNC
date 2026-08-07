import os
import pathlib
import logging
from tkinter import Variable
from CNC import CNC
import Utils

logScript = logging.getLogger("Script")
logScript.setLevel(logging.INFO)

REFERENCE_PERIOD = Utils.getFloat("Connection", "poll", 10)/1000

SCRIPT_SUFFIX = ".py"
SCRIPT_DIRNAME = "scripts"
# Files that live in scripts/ but are not user scripts.
SCRIPT_IGNORED = ("__init__.py",)


class ScriptEngine:
    def __init__(self, app) -> None:
        self.app = app

        self.scripts = {}
        # Directory the scripts were actually loaded from (None if not found).
        self.scriptsDir = None
        # name -> error string, for scripts present on disk that failed to load.
        self.failedScripts = {}
        self.loadScripts()

    # ------------------------------------------------------------------
    # Where scripts/ may live.
    #
    # Historically this was the hardcoded relative path 'scripts/', which
    # resolves against the *current working directory*. That silently loads
    # nothing when bCNC is started from anywhere other than the repo root,
    # which in turn makes user scripts (e.g. UserHome) disappear without any
    # error. Prefer paths derived from the installation, fall back to cwd.
    # ------------------------------------------------------------------
    def candidateDirs(self):
        candidates = []
        prgpath = getattr(Utils, "prgpath", None)
        if prgpath:
            # repo root / install root (scripts/ sits next to the bCNC package)
            candidates.append(os.path.join(
                os.path.dirname(prgpath), SCRIPT_DIRNAME))
            # inside the package, in case of a different layout
            candidates.append(os.path.join(prgpath, SCRIPT_DIRNAME))
        # legacy behaviour: relative to the current working directory
        candidates.append(SCRIPT_DIRNAME)

        ordered = []
        for path in candidates:
            path = os.path.abspath(path)
            if path not in ordered:
                ordered.append(path)
        return ordered

    def resolveScriptsDir(self):
        for path in self.candidateDirs():
            if os.path.isdir(path):
                return path
        return None

    # ------------------------------------------------------------------
    def loadScripts(self):
        self.scripts = {}
        self.failedScripts = {}
        self.scriptsDir = self.resolveScriptsDir()

        if self.scriptsDir is None:
            logScript.error(
                "No %s/ directory found, no user scripts loaded. Looked in: %s",
                SCRIPT_DIRNAME, ", ".join(self.candidateDirs()))
            return

        logScript.info("Loading scripts from %s", self.scriptsDir)

        try:
            entries = sorted(pathlib.Path(self.scriptsDir).iterdir())
        except OSError as exc:
            logScript.error(
                "Could not list script directory %s: %s", self.scriptsDir, exc)
            return

        for file in entries:
            # Skip directories and anything that is not a python script.
            # A single unreadable/binary file (e.g. a .DS_Store dropped in by
            # the file manager) must never stop the remaining scripts from
            # being loaded.
            if not file.is_file():
                continue
            if file.suffix.lower() != SCRIPT_SUFFIX:
                logScript.debug("Ignoring non-script file %s", file.name)
                continue
            if file.name in SCRIPT_IGNORED:
                continue

            name = self.scriptName(file.name)
            if not name:
                continue

            try:
                with open(str(file), encoding="utf-8") as fileObj:
                    content = fileObj.read()
            except Exception as exc:
                # Keep going: one broken script must not hide the others.
                self.failedScripts[name] = str(exc)
                logScript.error(
                    "Script %s FAILED to load from %s: %s",
                    name, file.name, exc)
                continue

            self.scripts[name] = content
            logScript.info("Script %s loaded", name)

        logScript.info(
            "%d script(s) loaded from %s (%d failed): %s",
            len(self.scripts), self.scriptsDir, len(self.failedScripts),
            ", ".join(sorted(self.scripts.keys())) or "none")

    # ------------------------------------------------------------------
    @staticmethod
    def scriptName(filename):
        """Map a file name to the key used in self.scripts."""
        dot = filename.find('.')
        if dot < 0:
            dot = len(filename)
        return filename[:dot].upper().strip()

    def find(self, name):
        name = name.upper().strip()
        return name in self.scripts.keys()

    def hasScriptFile(self, name):
        """True if a script file exists on disk, regardless of whether it
        was successfully loaded. Used to detect a load failure as opposed to
        the script genuinely not being installed."""
        wanted = name.upper().strip()
        for directory in self.candidateDirs():
            if not os.path.isdir(directory):
                continue
            try:
                entries = os.listdir(directory)
            except OSError:
                continue
            for entry in entries:
                if entry in SCRIPT_IGNORED:
                    continue
                if not entry.lower().endswith(SCRIPT_SUFFIX):
                    continue
                if self.scriptName(entry) == wanted:
                    return True
        return False

    def loadError(self, name):
        """Error string recorded for a script that failed to load, if any."""
        return self.failedScripts.get(name.upper().strip())

    def _setBindings(self, local, globa):
        local["execute"] = self.execCommand
        local["code"] = self.code
        local["wait"] = self.wait
        local["sleep"] = self.sleep
        local["get"] = self.get
        local["set"] = self.set
        local["exist"] = self.exist

    def execute(self, name, local, globa):
        name = name.upper().strip()
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
