# GRBL 1.0+ motion controller plugin

from __future__ import absolute_import
from __future__ import print_function
from _GenericGRBL import _GenericGRBL
from _GenericController import SPLITPAT, TOOLSPLITPAT, addExpectedReset
from CNC import CNC, WCS
from CNCRibbon import Page
import time
import Utils
from ThreadVar import ThreadVar

OV_FEED_100 = b'\x90'       # Extended override commands
OV_FEED_i10 = b'\x91'
OV_FEED_d10 = b'\x92'
OV_FEED_i1 = b'\x93'
OV_FEED_d1 = b'\x94'

OV_RAPID_100 = b'\x95'
OV_RAPID_i10 = b'\x96'
OV_RAPID_d10 = b'\x97'
OV_RAPID_d1 = b'\x98'

OV_SPINDLE_100 = b'\x99'
OV_SPINDLE_i10 = b'\x9A'
OV_SPINDLE_d10 = b'\x9B'
OV_SPINDLE_i1 = b'\x9C'
OV_SPINDLE_d1 = b'\x9D'

OV_SPINDLE_STOP = b'\x9E'

OV_FLOOD_TOGGLE = b'\xA0'
OV_MIST_TOGGLE = b'\xA1'


class Controller(_GenericGRBL):
    def __init__(self, master):
        self.gcode_case = 0
        self.has_override = True
        self.master = master
        self.reseted = False
        self.expectingReset = ThreadVar([])
        self.hasSD = False
        self.pidSP = 0
        self.pidTS = 0
        self.pidTarget = []
        self.pidActual = []
        self.pidError = []
        self.runOnceOnResetFunctions = []
        # print("grbl1 loaded")

    def jog(self, dir):
        self.master.sendGCode("$J=G91 %s F%s" % (
            dir, CNC.vars["JogSpeed"]))  # XXX is F100000 correct?

    def overrideSet(self):
        # Check feed
        diff = CNC.vars["_OvFeed"] - CNC.vars["OvFeed"]
        direction = diff > 0
        diff = abs(diff)
        while diff > 0:
            if diff >= 10:
                if direction:
                    self.master.serial_write(OV_FEED_i10)
                else:
                    self.master.serial_write(OV_FEED_d10)
                diff -= 10
                continue
            if diff >= 1:
                if direction:
                    self.master.serial_write(OV_FEED_i1)
                else:
                    self.master.serial_write(OV_FEED_d1)
                diff -= 1
        CNC.vars["OvFeed"] = CNC.vars["_OvFeed"]
        # Check rapid
        diff = CNC.vars["_OvRapid"] - CNC.vars["OvRapid"]
        direction = diff > 0
        diff = abs(diff)
        if CNC.vars["_OvRapid"] == 100 and diff > 0:
            self.master.serial_write(OV_RAPID_100)
            diff = 0
        while diff > 0:
            if diff >= 10:
                if direction:
                    self.master.serial_write(OV_RAPID_i10)
                else:
                    self.master.serial_write(OV_RAPID_d10)
                diff -= 10
                continue
            if diff >= 1:
                if direction:
                    self.master.serial_write(OV_RAPID_i10)
                    diff = 10 - diff
                    direction = not direction
                    continue
                self.master.serial_write(OV_RAPID_d1)
                diff -= 1
        CNC.vars["OvRapid"] = CNC.vars["_OvRapid"]
        # Check Spindle
        diff = CNC.vars["_OvSpindle"] - CNC.vars["OvSpindle"]
        direction = diff > 0
        diff = abs(diff)
        while diff > 0:
            if diff >= 10:
                if direction:
                    self.master.serial_write(OV_SPINDLE_i10)
                else:
                    self.master.serial_write(OV_SPINDLE_d10)
                diff -= 10
                continue
            if diff >= 1:
                if direction:
                    self.master.serial_write(OV_SPINDLE_i1)
                else:
                    self.master.serial_write(OV_SPINDLE_d1)
                diff -= 1
        CNC.vars["OvSpindle"] = CNC.vars["_OvSpindle"]
        self.master.serial.flush()

    def parseBracketAngle(self, line, ioData):
        ioData.decrementSioCount()
        fields = line[1:-1].split("|")
        CNC.vars["pins"] = ""

        # Report if state has changed
        if CNC.vars["state"] != fields[0] or self.master.runningPrev != self.master.running:
            self.master.controllerStateChange(fields[0])
        self.master.runningPrev = self.master.running

        self.displayState(fields[0])

        for field in fields[1:]:
            word = SPLITPAT.split(field)
            if word[0] == "MPos":
                try:
                    CNC.vars["mx"] = float(word[1])
                    CNC.vars["my"] = float(word[2])
                    CNC.vars["mz"] = float(word[3])
                    CNC.vars["wx"] = round(
                        CNC.vars["mx"]-CNC.vars["wcox"], CNC.digits)
                    CNC.vars["wy"] = round(
                        CNC.vars["my"]-CNC.vars["wcoy"], CNC.digits)
                    CNC.vars["wz"] = round(
                        CNC.vars["mz"]-CNC.vars["wcoz"], CNC.digits)
                    # if Utils.config.get("bCNC","enable6axis") == "true":
                    if len(word) > 4:
                        CNC.vars["ma"] = float(word[4])
                        CNC.vars["wa"] = round(
                            CNC.vars["ma"]-CNC.vars["wcoa"], CNC.digits)
                    if len(word) > 5:
                        CNC.vars["mb"] = float(word[5])
                        CNC.vars["wb"] = round(
                            CNC.vars["mb"]-CNC.vars["wcob"], CNC.digits)
                    if len(word) > 6:
                        CNC.vars["mc"] = float(word[6])
                        CNC.vars["wc"] = round(
                            CNC.vars["mc"]-CNC.vars["wcoc"], CNC.digits)
                    self.master._posUpdate = True
                except (ValueError, IndexError):
                    CNC.vars["state"] = "Garbage receive %s: %s" % (
                        word[0], line)
                    self.master.log.put(
                        (self.master.MSG_RECEIVE, CNC.vars["state"]))
                    break
            elif word[0] == "F":
                try:
                    CNC.vars["curfeed"] = float(word[1])
                except (ValueError, IndexError):
                    CNC.vars["state"] = "Garbage receive %s: %s" % (
                        word[0], line)
                    self.master.log.put(
                        (self.master.MSG_RECEIVE, CNC.vars["state"]))
                    break
            elif word[0] == "FS":
                try:
                    CNC.vars["curfeed"] = float(word[1])
                    CNC.vars["curspindle"] = float(word[2])
                    if len(word) > 3:
                        CNC.vars["realRpm"] = float(word[3])
                except (ValueError, IndexError):
                    CNC.vars["state"] = "Garbage receive %s: %s" % (
                        word[0], line)
                    self.master.log.put(
                        (self.master.MSG_RECEIVE, CNC.vars["state"]))
                    break
            elif word[0] == "Bf":
                try:
                    CNC.vars["planner"] = int(word[1])
                    CNC.vars["rxbytes"] = int(word[2])
                except (ValueError, IndexError):
                    CNC.vars["state"] = "Garbage receive %s: %s" % (
                        word[0], line)
                    self.master.log.put(
                        (self.master.MSG_RECEIVE, CNC.vars["state"]))
                    break
            elif word[0] == "Ov":
                try:
                    CNC.vars["OvFeed"] = int(word[1])
                    CNC.vars["OvRapid"] = int(word[2])
                    CNC.vars["OvSpindle"] = int(word[3])
                except (ValueError, IndexError):
                    CNC.vars["state"] = "Garbage receive %s: %s" % (
                        word[0], line)
                    self.master.log.put(
                        (self.master.MSG_RECEIVE, CNC.vars["state"]))
                    break
            elif word[0] == "WCO":
                try:
                    CNC.vars["wcox"] = float(word[1])
                    CNC.vars["wcoy"] = float(word[2])
                    CNC.vars["wcoz"] = float(word[3])
                    # if Utils.config.get("bCNC","enable6axis") == "true":
                    if len(word) > 4:
                        CNC.vars["wcoa"] = float(word[4])
                    if len(word) > 5:
                        CNC.vars["wcob"] = float(word[5])
                    if len(word) > 6:
                        CNC.vars["wcoc"] = float(word[6])
                except (ValueError, IndexError):
                    CNC.vars["state"] = "Garbage receive %s: %s" % (
                        word[0], line)
                    self.master.log.put(
                        (self.master.MSG_RECEIVE, CNC.vars["state"]))
                    break
            elif word[0] == "Ln":
                CNC.vars["line"] = int(word[1])
            elif word[0] == "Pn":
                try:
                    CNC.vars["pins"] = word[1]
                    if 'S' in word[1]:
                        if CNC.vars["state"] == 'Idle' and not self.master.running:
                            print("Stream requested by CYCLE START machine button")
                            self.master.event_generate("<<Run>>", when='tail')
                        else:
                            print("Ignoring machine stream request, because of state: ",
                                  CNC.vars["state"], self.master.running)
                except (ValueError, IndexError):
                    break
            elif word[0] == "In":
                print("Input = {}".format(word[1]))
                pass
            elif word[0] == "Inps":
                try:
                    CNC.vars["inputs"] = int(word[1])
                except (ValueError, IndexError):
                    break
        # Machine is Idle buffer is empty stop waiting and go on
        if ioData.sio_wait and ioData.sumCline == 0 and sum([1 if w in fields[0] else 0 for w in ("Run", "Jog", "Hold")]) == 0:
            # if not self.master.running: self.master.jobDone() #This is not a good idea, it purges the controller while waiting for toolchange. see #1061
            ioData.sio_wait = False
            self.master._gcount.assign(lambda x: x + 1)

    def parseBracketSquare(self, line):
        word = SPLITPAT.split(line[1:-1])
        # print word
        if word[0] == "PRB":
            CNC.vars["prbx"] = float(word[1])
            CNC.vars["prby"] = float(word[2])
            CNC.vars["prbz"] = float(word[3])
            # if self.running:
            self.master.gcode.probe.add(
                CNC.vars["prbx"]-CNC.vars["wcox"],
                CNC.vars["prby"]-CNC.vars["wcoy"],
                CNC.vars["prbz"]-CNC.vars["wcoz"])
            self.master._probeUpdate = True
            CNC.vars[word[0]] = word[1:]
        if word[0] in WCS:
            workId = WCS.index(word[0])+1
            CNC.vars["workTable"][workId] = [float(w) for w in word[1:]]
            self.onRecieveWork(workId, CNC.vars["workTable"][workId])
        if word[0] in ["G59.1", "G59.2", "G59.3"]:
            workId = int(word[0][1:3]) + int(word[0][4:])-53
            CNC.vars["workTable"][workId] = [float(w) for w in word[1:]]
            self.onRecieveWork(workId, CNC.vars["workTable"][workId])
        if word[0] == "G92":
            CNC.vars["G92X"] = float(word[1])
            CNC.vars["G92Y"] = float(word[2])
            CNC.vars["G92Z"] = float(word[3])
            # if Utils.config.get("bCNC","enable6axis") == "true":
            if len(word) > 4:
                CNC.vars["G92A"] = float(word[4])
            if len(word) > 5:
                CNC.vars["G92B"] = float(word[5])
            if len(word) > 6:
                CNC.vars["G92C"] = float(word[6])
            CNC.vars[word[0]] = word[1:]
            self.master._gUpdate = True
        if word[0] == "G28":
            CNC.vars["G28X"] = float(word[1])
            CNC.vars["G28Y"] = float(word[2])
            CNC.vars["G28Z"] = float(word[3])
            CNC.vars[word[0]] = word[1:]
            self.master._gUpdate = True
        if word[0] == "G30":
            CNC.vars["G30X"] = float(word[1])
            CNC.vars["G30Y"] = float(word[2])
            CNC.vars["G30Z"] = float(word[3])
            CNC.vars[word[0]] = word[1:]
            self.master._gUpdate = True
        elif word[0] == "GC":
            CNC.vars["G"] = word[1].split()
            CNC.updateG()
            self.master._gUpdate = True
        elif word[0] == "TLO":
            CNC.vars[word[0]] = word[1]
            self.master._probeUpdate = True
            self.master._gUpdate = True
        elif word[0] == "PID":
            self.pidSP = word[1]
            self.pidTS = word[2]
            self.pidTarget = []
            self.pidActual = []
            self.pidError = []
            self.pid = []
            fir = True
            try:
                for i in range(3, len(word), 3):
                    w = word[i]
                    wP = word[i+1]
                    wS = word[i+2]
                    if fir:
                        fir = False
                        w = w[w.find('|')+1:]
                    self.pidTarget += [float(w)]
                    self.pidActual += [float(wP)]
                    self.pidError += [float(wS)]
            except:
                pass
        elif word[0] == "Pitch":
            try:
                CNC.vars["pitch"] = float(word[1])
            except:
                CNC.vars["pitch"] = -1
        elif word[0] == "T":
            toolWord = TOOLSPLITPAT.split(line[1:-1])
            id = int(toolWord[1])
            CNC.vars["toolTable"][id] = [float(w) for w in toolWord[2:]]
            self.onRecieveTool(id, CNC.vars["toolTable"][id])
        else:
            CNC.vars[word[0]] = word[1:]
            if word[0] == "MSG" and word[1] == "Disabled":
                self.expectingReset.execute(addExpectedReset)
