# Generic motion controller definition
# All controller plugins inherit features from this one

from __future__ import absolute_import
from __future__ import print_function

from CNC import CNC, WCS
from CNCRibbon import Page
import Utils
import os.path
import time
import re
import threading

import tkinter
from mttkinter import *
# GRBLv1
SPLITPAT = re.compile(r"[:,]")
TOOLSPLITPAT = re.compile(r"[:|,]")

# GRBLv0 + Smoothie
STATUSPAT = re.compile(
    r"^<(\w*?),MPos:([+\-]?\d*\.\d*),([+\-]?\d*\.\d*),([+\-]?\d*\.\d*)(?:,[+\-]?\d*\.\d*)?(?:,[+\-]?\d*\.\d*)?(?:,[+\-]?\d*\.\d*)?,WPos:([+\-]?\d*\.\d*),([+\-]?\d*\.\d*),([+\-]?\d*\.\d*)(?:,[+\-]?\d*\.\d*)?(?:,[+\-]?\d*\.\d*)?(?:,[+\-]?\d*\.\d*)?(?:,.*)?>$")
POSPAT = re.compile(
    r"^\[(...):([+\-]?\d*\.\d*),([+\-]?\d*\.\d*),([+\-]?\d*\.\d*)(?:,[+\-]?\d*\.\d*)?(?:,[+\-]?\d*\.\d*)?(?:,[+\-]?\d*\.\d*)?(:(\d*))?\]$")
TLOPAT = re.compile(r"^\[(...):([+\-]?\d*\.\d*)\]$")
DOLLARPAT = re.compile(r"^\[G\d* .*\]$")

# Only used in this file
VARPAT = re.compile(r"^\$(\d+) *= *(\d*\.?\d*) *\(?.*")

global lastTime
lastTime = time.time()


class _GenericController:
    def test(self):
        print("test supergen")

    def executeCommand(self, oline, line, cmd):
        return False

    def registerRunOnceOnReset(self, function):
        self.runOnceOnResetFunctions.append(function)

    def onRecieveSetting(self, id, value):
        if self.validSetting(id, value):
            return
        self.sendSetting(id)

    def onRecieveTool(self, id, off):
        if self.validTool(id, off):
            return
        self.sendTool(id)

    def onRecieveWork(self, id, off):
        if self.validWork(id, off):
            return
        self.sendWork(id)

    def onReset(self):
        self.master.stopProbe()
        self.master.runEnded()
        CNC.vars["_OvChanged"] = True  # force a feed change if any
        self.unlock()
        while len(self.runOnceOnResetFunctions):
            self.runOnceOnResetFunctions[0]()
            del self.runOnceOnResetFunctions[0]
        if not self.expectingReset:
            tkinter.messagebox.showerror(
                "Erro", "Controlador foi resetado sem a devida instrução")
            pass
        self.expectingReset = False

    def hardResetPre(self):
        pass

    def hardResetAfter(self):
        pass

    def viewStartup(self):
        pass

    def checkGcode(self):
        pass

    def viewSettings(self):
        pass

    def grblRestoreSettings(self):
        pass

    def grblRestoreWCS(self):
        pass

    def grblRestoreAll(self):
        pass

    def purgeControllerExtra(self):
        pass

    def overrideSet(self):
        pass

    def hardReset(self):
        self.master.busy()
        if self.master.serial is not None:
            self.hardResetPre()
            self.master.openClose()
            self.hardResetAfter()
        self.master.openClose()
        self.master.stopProbe()
        self.master._alarm.value = False
        CNC.vars["_OvChanged"] = True  # force a feed change if any
        self.master.notBusy()
        self.viewParameters()

    # ----------------------------------------------------------------------
    def softReset(self, clearAlarm=True):
        if not self.master.serial:
            return
        self.expectingReset = True
        self.master.serial_write(b"\x18")
        self.master.serial.flush()

    # ----------------------------------------------------------------------
    def clearError(self):
        self.master.deque.append("?$X?\n")

    # ----------------------------------------------------------------------
    def unlock(self, clearAlarm=True):
        if clearAlarm:
            self.master._alarm.value = False
        self.clearError()
        self.viewParameters()

    # ----------------------------------------------------------------------
    def home(self, event=None):
        self.master._alarm.value = False

        if self.master.scripts.find("UserHome"):
            self.master.executeCommand("UserHome")
        else:
            self.master.sendGCode("$H")

    def viewStatusReport(self):
        self.master.serial_write(b'\x80')
        self.master.serial.flush()

    def viewConfiguration(self):
        self.master.sendGCode("$$")

    def saveSettings(self):
        flag = 'x'
        if os.path.isfile("Settings.txt"):
            return
        with open("Settings.txt", flag) as file:
            file.write("$0 = 5\n")

    @staticmethod
    def verifyEquality(value0, value1):
        if value0 is None or value1 is None:
            return False
        value0 = float(value0)
        value1 = float(value1)
        return abs(value0 - value1) <= 0.001

    def validSetting(self, id, mcuValue):  # TODO: please, do this the proper way
        allSettings = self.getSettings()
        for setting in allSettings:
            pat = VARPAT.match(setting)
            if not pat:
                continue
            if int(pat.group(1)) == int(id):
                response = _GenericController.verifyEquality(
                    pat.group(2), mcuValue)
                if not response:
                    print("Is not valid |{}|!=|{}|".format(
                        mcuValue, pat.group(2)))
                return response
        return True

    def sendSetting(self, id):  # TODO: Please, do this the proper way
        allSettings = self.getSettings()
        for setting in allSettings:
            pat = VARPAT.match(setting)
            if not pat:
                continue
            if int(pat.group(1)) != int(id):
                continue
            value = float(pat.group(2))
            if _GenericController.verifyEquality(value, int(value)):
                value = int(value)
            cmd = "${}={}\n".format(int(id), value)
            self.master.sendGCode(cmd)
            self.master.sendGCode((4,))
            return

    def sendSettings(self):
        settings = self.getSettings()
        self.clearError()
        CNC.vars["radius"] = Utils.getStr("CNC", "radius", "G90")
        for settingsUnit in settings:
            self.master.deque.append(settingsUnit+'\n')
        self.master.log.put((self.master.MSG_OK, "Configuration OK"))

    def getSettings(self):
        if not os.path.isfile("Settings.txt"):
            self.saveSettings()
        settings = []
        with open("Settings.txt", 'r') as settingsFile:
            for line in settingsFile.readlines():
                settings += [line]
        return settings

    def viewParameters(self):
        self.master.sendGCode("$$")
        self.master.sendGCode("$#")

    def validTool(self, id, mcuOff):
        axis = "xyzabc"
        compensationTable = self.master.compensationTable.getTable()
        toolTable = self.master.toolTable.getTable()
        for tool, compensation in zip(toolTable, compensationTable):
            if int(tool["index"]) != int(id):
                continue
            wantedOff = []
            for axe in axis:
                value = float(tool[axe]) + float(compensation[axe])
                wantedOff += [value]
            skip = True
            for i in range(0, min(len(wantedOff), len(mcuOff))):
                skip = skip and _GenericController.verifyEquality(
                    wantedOff[i], mcuOff[i])
            if not skip:
                print("Tool {} is not the same as mcu value: mcu={}; rasp={};".format(
                    id, mcuOff, wantedOff))
            return skip
        return True

    def sendTool(self, id):
        axis = Utils.getStr("CNC", "axis", "xyzabc").lower()
        compensationTable = self.master.compensationTable.getTable()
        toolTable = self.master.toolTable.getTable()
        for tool, compensation in zip(toolTable, compensationTable):
            if int(tool["index"]) != int(id):
                continue
            cmd = "G10L1P{}".format(tool['index'])
            for axe in axis:
                if axe in tool.keys():
                    val = float(tool[axe]) + float(compensation[axe])
                    cmd += "%c%.3f" % (axe.upper(), float(val))
            self.master.sendGCode(cmd)
            self.master.sendGCode((4,))
            self.master.sendGCode("G43")
            return

    def validWork(self, id, mcuOff):
        axis = "xyzabc"
        workTable = self.master.workTable.getTable()
        for work in workTable:
            if int(work["index"]) != int(id):
                continue
            wantedOff = []
            for axe in axis:
                wantedOff += [work[axe]]
            skip = True
            for i in range(0, min(len(wantedOff), len(mcuOff))):
                skip = skip and _GenericController.verifyEquality(
                    wantedOff[i], mcuOff[i])
            if not skip:
                print("WCS {} is not the same as mcu value: mcu={}; rasp={};".format(
                    id, mcuOff, wantedOff))
            return skip
        return True

    def sendWork(self, id):
        axis = Utils.getStr("CNC", "axis", "xyzabc").lower()
        workTable = self.master.workTable.getTable()
        for work in workTable:
            if int(work["index"]) != int(id):
                continue
            cmd = "G10L2P{}".format(work['index'])
            for axe in axis:
                if axe in work.keys():
                    cmd += "%c%.3f" % (axe.upper(), float(work[axe]))
            self.master.sendGCode(cmd)
            self.master.sendGCode((4,))
            return

    def viewState(self):  # Maybe rename to viewParserState() ???
        self.master.sendGCode("$G")

    # ----------------------------------------------------------------------
    def jog(self, dir):
        # print("jog",dir)
        self.master.sendGCode("G91G0%s" % (dir))
        self.master.sendGCode("G90")

    # ----------------------------------------------------------------------
    def goto(self, x=None, y=None, z=None, a=None, b=None, c=None):
        cmd = "G90G0"
        if x is not None:
            cmd += "X%g" % (x)
        if y is not None:
            cmd += "Y%g" % (y)
        if z is not None:
            cmd += "Z%g" % (z)
        if a is not None:
            cmd += "A%g" % (a)
        if b is not None:
            cmd += "B%g" % (b)
        if c is not None:
            cmd += "C%g" % (c)
        self.master.sendGCode("%s" % (cmd))

    def _toolCompensate(self, toolNumber=None, x=None, y=None, z=None,
                        a=None, b=None, c=None):
        compensation = self.master.compensationTable
        table = compensation.getTable()
        if toolNumber is None:
            toolNumber = int(CNC.vars["tool"])
        if toolNumber == 0:
            return
        row, index = compensation.getRow(toolNumber)
        if index == -1:  # assume that this function only adds one entry to tool table
            table.append({'index', toolNumber})
        axis = "xyzabc"
        vars = [x, y, z, a, b, c]
        for (name, value) in zip(axis, vars):
            if value is not None:
                table[index][name] = value
        compensation.save(table)
        self.sendTool(toolNumber)

    def getCurrentToolOffset(self):
        index = CNC.vars["tool"]
        if index == 0:
            return [0.000]*6
        tool, index = self.master.toolTable.getRow(index)
        return tool

    def _tloSet(self, toolNumber=None, x=None, y=None,
                z=None, a=None, b=None, c=None):
        tools = self.master.toolTable
        table = tools.getTable()
        if toolNumber is None:
            toolNumber = int(CNC.vars["tool"])
        if toolNumber == 0:
            return
        tool, index = tools.getRow(toolNumber)
        if index == -1:  # assume that this function only adds one entry to tool table
            table.append({'index': toolNumber})
        print(tool)
        axis = "xyzabc"
        vars = [x, y, z, a, b, c]
        for (name, value) in zip(axis, vars):
            if value is not None:
                table[index][name] = value
        tools.save(table)
        self.sendTool(toolNumber)

    # ----------------------------------------------------------------------
    def _wcsSet(self, x=None, y=None, z=None, a=None, b=None, c=None, wcsIndex=None):
        workTable = self.master.workTable.getTable()
        radiusMode = CNC.vars["radius"]

        # global wcsvar
        # p = wcsvar.get()
        if wcsIndex is None:
            p = WCS.index(CNC.vars["WCS"])
        else:
            p = wcsIndex

        work, index = self.master.workTable.getRow(p+1)
        workTable[index]["r"] = radiusMode

        cmd = ""
        if p < 6:
            cmd = "G10L2P%d" % (p+1)
        elif p == 6:
            cmd = "G28.1"
        elif p == 7:
            cmd = "G30.1"
        elif p == 8:
            cmd = "G92"

        pos = ""
        if x is not None and abs(float(x)) < 10000.0:
            workTable[index]['x'] = str(CNC.vars['mx'] - float(x))
            pos += "X"+workTable[index]['x']
        if y is not None and abs(float(y)) < 10000.0:
            workTable[index]['y'] = str(CNC.vars['my'] - float(y))
            pos += "Y"+workTable[index]['y']
        if z is not None and abs(float(z)) < 10000.0:
            workTable[index]['z'] = str(CNC.vars['mz'] - float(z))
            pos += "Z"+workTable[index]['z']
        if a is not None and abs(float(a)) < 10000.0:
            workTable[index]['a'] = str(CNC.vars['ma'] - float(a))
            pos += "A"+workTable[index]['a']
        if b is not None and abs(float(b)) < 10000.0:
            workTable[index]['b'] = str(CNC.vars['mb'] - float(b))
            pos += "B"+workTable[index]['b']
        if c is not None and abs(float(c)) < 10000.0:
            workTable[index]['c'] = str(CNC.vars['mc'] - float(c))
            pos += "C"+workTable[index]['c']
        cmd += pos
        self.master.workTable.save(workTable)
        self.sendWork(p+1)

        self.viewParameters()
        self.master.event_generate("<<Status>>",
                                   data=(_("Set workspace %s to %s") % (WCS[p], pos)))
        # data=(_("Set workspace %s to %s")%(WCS[p],pos)))
        self.master.event_generate("<<CanvasFocus>>")

    # ----------------------------------------------------------------------
    def feedHold(self, event=None):
        if self.master.serial is None:
            return
        self.master.serial_write(b'!')
        self.master.serial.flush()
        self.master._pause.value = True

    # ----------------------------------------------------------------------
    def resume(self, event=None):
        if event is not None and not self.master.acceptKey(True):
            return
        if self.master.serial is None:
            return
        self.master.serial_write(b'~')
        self.master.serial.flush()
        self.master._msg.value = None
        self.master._alarm.value = False
        self.master._pause.value = False

    # ----------------------------------------------------------------------
    def pause(self, event=None):
        if self.master.serial is None:
            return
        if self.master._pause.value:
            self.master.resume()
        else:
            self.master.feedHold()

    # ----------------------------------------------------------------------
    # Purge the buffer of the controller. Unfortunately we have to perform
    # a reset to clear the buffer of the controller
    # ---------------------------------------------------------------------
    def purgeController(self):
        def function():
            self.master.runEnded()
            self.master.stopProbe()
            self.master.sendGCode("?")
            self.master.sendGCode("$X")
            self.master.sendGCode("?")
            self.viewState()
        self.registerRunOnceOnReset(function)
        self.softReset(False)			# reset controllerGeneric

    # ----------------------------------------------------------------------

    def displayState(self, state):
        state = state.strip()

        # Do not show g-code errors, when machine is already in alarm state
        if (CNC.vars["state"].startswith("ALARM:") and state.startswith("error:")):
            print("Supressed: %s" % (state))
            return

        # Do not show alarm without number when we already display alarm with number
        if (state == "Alarm" and CNC.vars["state"].startswith("ALARM:")):
            return

        CNC.vars["state"] = state

    # ----------------------------------------------------------------------

    def parseLine(self, line, ioData):
        if not line:
            return True

        elif line[0] == "<":
            if CNC.vars["debug"]:
                self.master.log.put((self.master.MSG_RECEIVE, line))
            self.parseBracketAngle(line, ioData)
            if "door" in line.lower():
                if self.master.running.value:
                    errorLine = CNC.vars["errline"]
                    self.feedHold()
                    self.master._stop.value = True
                    self.master.stopRun()
                    self.master.runEnded()
                    tkinter.messagebox.showerror(
                        "Erro", "Erro inesperado na linha "+errorLine + "\n")

        elif "pgm end" in line.lower():
            CNC.vars["pgmEnd"] = True

        elif line[0] == "[":
            self.master.log.put((self.master.MSG_RECEIVE, line))
            self.parseBracketSquare(line)

        elif "error:" in line or "ALARM:" in line:
            self.master.log.put((self.master.MSG_ERROR, line))
            self.master._gcount.assign(lambda x: x + 1)
            # print "gcount ERROR=",self._gcount
            CNC.vars["errline"] = ioData.deleteFirstLine()
            if not self.master._alarm.value:
                self.master._posUpdate = True
            self.master._alarm.value = True
            self.displayState(line)
            if self.master.running.value:
                errorLine = CNC.vars["errline"]
                self.feedHold()
                self.master._stop.value = True
                self.master.stopRun()
                self.master.runEnded()
                tkinter.messagebox.showerror(
                    "Erro", "Erro inesperado na linha "+errorLine + "\n")

        elif line.find("ok") >= 0:
            self.master.log.put((self.master.MSG_OK, line))
            self.master._gcount.assign(lambda x: x + 1)
            ioData.deleteFirstLine()
            # print "SLINE:",sline
# if  self._alarm and not self.running:
# # turn off alarm for connected status once
# # a valid gcode event occurs
# self._alarm = False

        elif line[0] == "$":
            self.master.log.put((self.master.MSG_RECEIVE, line))
            pat = VARPAT.match(line)
            if pat:
                CNC.vars["grbl_%s" % (pat.group(1))] = pat.group(2)
                self.onRecieveSetting(int(pat.group(1)), float(pat.group(2)))

        # and self.running:
        elif line[:4] == "Grbl" or line[:13] == "CarbideMotion":
            # tg = time.time()
            self.master.log.put((self.master.MSG_RECEIVE, line))
            self.master._stop.value = True
            ioData.sio_count = 0
            ioData.clear()
            CNC.vars["version"] = line.split()[1]
            # Detect controller
            if self.master.controller in ("GRBL0", "GRBL1"):
                self.master.controllerSet(
                    "GRBL%d" % (int(CNC.vars["version"][0])))
            self.master.onStopComplete.value = self.onReset
        else:
            # We return false in order to tell that we can't parse this line
            # Sender will log the line in such case
            return False

        # Parsing succesfull
        return True
