import abc
import threading
import time
import Utils
import io
import logging

from CNC import CNC

import tkinter

from mttkinter import *

def getArrayWhileExists(section, preffix, method=Utils.getInt, default=-20):
    values = []
    index = 0
    while 1:
        id = preffix + str(index)
        values += [method(section, id, default)]
        if values[-1] == default:
            del values[-1]
            break
        index += 1
    return values

def getArrayFromUtils(section, array, method=Utils.getInt, default=-20):
    values = []
    for w in array:
        values += [method(section, w, default)]
    return values


class Jog(MemberImpl):
    JOGMOTION = 0
    JOGSTOP = 1
    def __init__(self, app):
        self.active = Utils.getBool("Jog", "panel", False)

        self.type = Utils.getBool("Jog", "directionMode", True)
        #directionMode:
        # pin0: axis
        # pin1: direction
        #
        # directMode:
        # pin0: axis+
        # pin1: axis-

        self.axisMap = "XYZABC"
        self.directionMap = {0: "Up", 1: "Down"}

        self.directMappings = []
        for w in self.axisMap:
            self.directMappings += [w+"Up",w+"Down"]

        self.jogLastAction = self.JOGMOTION
        debounce = Utils.getFloat("Jog", "debounce", 0.05)
        self.plannerLimit = Utils.getInt("Jog","planner", 90)

        pins, inversion = self.load_pins()
        self.lastPinValues = []

        logPanel.info("Jog Member: ")
        super().__init__(app, pins, inversion, debounce, self.callback, self.active)

    def load_pins(self):
        pins = []
        inversion = 0
        arr = []
        if self.type:
            for w in self.axisMap:
                arr += [w, w+"dir"]
        else:
            arr = self.directMappings
        pins = getArrayFromUtils("Jog", arr, Utils.getInt, -20)
        inversion = Utils.getInt("Jog", "inversion", 0)
        return pins, inversion

    def directionMode(self, pinValues):
        axis = []
        direction = []
        for i in range(0,len(pinValues)):
            if i % 2 == 0: axis += [pinValues[i]]
            else: direction += [pinValues[i]]
        for id, (axe,dire) in enumerate(zip(axis,direction)):
            if axe == 1:
                con = self.axisMap[id] + self.directionMap[dire]
                code = self.app.jogController.mapKeyToCode[con][0]
                codeWrapper = tkinter.EventType.KeyPress, code
                self.app.jogController.jogEvent(simulatedData = codeWrapper)
                #self.app.jogController
                #self.app.jogMutex.acquire()
                #self.app.focus_set()
                #self.app.event_generate("<<"+con+">>", when="tail")
                #self.jogLastAction = self.JOGMOTION
                #self.app.jogMutex.acquire(blocking=True)
                #self.app.jogMutex.release()
                return

    def directMode(self, pinValues):
        data = ""
        for id, val in enumerate(pinValues):
            if val == 1:
                con = self.directMappings[id]
                if len(data)>2:
                    if data[-2]==con[0]:
                        continue
                data += con[0]
                data += '+' if con[1:] == "Up" else '-'
        if len(data) == 0:
            return
        for i in range(0, len(data),2):
            key = data[i:i+2]
            code = self.app.jogController.mapKeyToCode[key][0]
            codeWrapper = tkinter.EventType.KeyPress, code
            self.app.jogController.jogEvent(simulatedData = codeWrapper)
        #self.app.jogMutex.acquire()
        #self.app.focus_set()
        #self.app.jogData = data
        #self.app.event_generate("<<JOG>>", when="tail")
        #self.jogLastAction = self.JOGMOTION
        #self.app.jogMutex.acquire(blocking=True)
        #self.app.jogMutex.release()

    def callback(self, pinValues):
        shouldStop = False
        if len(self.lastPinValues) == len(pinValues):
            for (a,b) in zip(self.lastPinValues, pinValues):
                if a!=b:
                    shouldStop = True
        self.lastPinValues = pinValues
        if shouldStop:
            return
        #if shouldStop and self.jogLastAction != self.JOGSTOP:
        #    self.app.jogMutex.acquire()
        #    self.app.focus_set()
        #    self.app.event_generate("<<JogStop>>", when="tail")
        #    self.jogLastAction = self.JOGSTOP
        #    self.app.jogMutex.acquire(blocking=True)
        #    self.app.jogMutex.release()
        #    return
        if self.type == True:
            self.directionMode(pinValues)
        else:
            self.directMode(pinValues)

class Selector(MemberImpl):
    def __init__(self, app, index, onChange) -> None:
        self.onChange = onChange
        self.selectorIndex = index
        self.selectorName = "Selector{}".format(index)
        self.active = Utils.getBool(self.selectorName, "panel", False)
        debounce = Utils.getFloat(self.selectorName, "debounce", 0.1)
        self.selectorBinaryType = Utils.getBool(self.selectorName, "binary", False)
        self.grayCodeActive = Utils.getBool(self.selectorName, "gray", False)

        binary =  lambda index, id: index + (2**id)
        direct = lambda index, id: id
        self.typeFunction = binary if self.selectorBinaryType else direct

        self.variableBegin = Utils.getFloat(self.selectorName, "begin", -1)
        self.variableEnd = Utils.getFloat(self.selectorName, "end", -1)
        self.variableOptions = getArrayWhileExists(self.selectorName, "v", Utils.getFloat, 0)

        pins, inversion = self.load_pins()

        self.useBeginEnd = self.variableBegin!=-1
        self.resolution = len(pins)
        if self.selectorBinaryType:
            self.resolution = 2**self.resolution-1
        self.resolution = Utils.getInt(self.selectorName, "resolution", self.resolution)

        logPanel.info(self.selectorName + " Member: ")
        if self.useBeginEnd:
            self.currentVar = self.variableBegin
        else:
            self.currentVar = self.variableOptions[0]
        super().__init__(app, pins, inversion, debounce, self.callback, self.active)

    def load_pins(self):
        pins = getArrayWhileExists(self.selectorName, "pin", Utils.getInt, -20)
        inversion = Utils.getInt(self.selectorName, "inversion", 0)
        return pins, inversion

    @staticmethod
    def grayToBinary(num):
        num ^= num >> 16
        num ^= num >> 8
        num ^= num >> 4
        num ^= num >> 2
        num ^= num >> 1
        return num

    def calculateIndex(self, selector: list):
        index = 0
        for id, w in enumerate(selector):
            if w == 1:
                index = self.typeFunction(index, id)
        if self.grayCodeActive:
            index = Selector.grayToBinary(index)
        return index

    def callback(self, selector: list):
        index = self.calculateIndex(selector)
        var = 0
        if self.useBeginEnd:
            var = (self.variableEnd - self.variableBegin)/self.resolution
            var = var*index + self.variableBegin
        else:
            var = self.variableOptions[index]
        if var != self.currentVar:
            self.currentVar = var
            self.onChange()

class StepSelector(Selector):
    def __init__(self, app, index) -> None:
         super().__init__(app, index, self.onChange)
    def onChange(self):
        self.app.control.setStep(self.currentVar)

class FeedSelector(Selector):
    def __init__(self, app, index, names = ["Feed"]) -> None:
         super().__init__(app, index, self.onChange)
         self.names = names

    def change(self, name, var):
        self.app.gstate.setOverride(name,var)

    def onChange(self):
        for w in self.names:
            self.change(w, self.currentVar)
        self.app.mcontrol.overrideSet()

class RapidSelector(Selector):
    def __init__(self, app, index, names = ["Rapid"]) -> None:
         super().__init__(app, index, self.onChange)
         self.names = names

    def change(self, name, var):
        self.app.gstate.setOverride(name,var)

    def onChange(self):
        for w in self.names:
            self.change(w, self.currentVar)
        self.app.mcontrol.overrideSet()

class ButtonPanel(MemberImpl):
    def __init__(self, app, index) -> None:
        self.panelName = "Button{}".format(index)
        self.description = Utils.getStr(self.panelName, "name", self.panelName)
        self.active = Utils.getBool(self.panelName, "panel", False)
        debounce = Utils.getFloat(self.panelName, "debounce", 0.5)
        pins, inversion = self.load_pins()
        logPanel.info("Button%d Member:" % (index))
        self.lastState = [0]
        self.onOnExecute = Utils.getStr(self.panelName, "on", "")
        self.onOffExecute = Utils.getStr(self.panelName, "off", "")
        super().__init__(app,pins, inversion, debounce, self.callback, self.active)

    def load_pins(self):
        pins = [Utils.getInt(self.panelName, "pin", -20)]
        inversion = Utils.getInt(self.panelName, "inversion", 0)
        return pins, inversion

    def callback(self, buttons: list):
        state = 0
        if len(buttons):
            state = buttons[0]
        if state == self.lastState:
            return
        self.lastState = state
        if state == 0:
            self.off()
            return
        self.on()
    def on(self):
        self.app.execute(self.onOnExecute)
    def off(self):
        self.app.execute(self.onOffExecute)


class StartButton(ButtonPanel):
    def __init__(self, app, index) -> None:
         super().__init__(app, index)
    def on(self):
        if CNC.vars["state"] == "Idle" and not self.app.running.value and CNC.vars["execution"]:
            self.app.focus_set()
            self.app.event_generate("<<Run>>", when="tail")
        elif "hold" in CNC.vars["state"].lower():
            self.app.resume()

class PauseButton(ButtonPanel):
    def __init__(self, app, index) -> None:
         super().__init__(app, index)
         self.lastState = 0
    def on(self):
        self.app.feedHold()

class StartPauseButton(ButtonPanel):
    def __init__(self, app, index) -> None:
         super().__init__(app, index)
    def on(self):
        if CNC.vars["state"] == "Idle" and not self.app.running.value and CNC.vars["execution"]:
            self.app.focus_set()
            self.app.event_generate("<<Run>>", when="tail")
        else:
            self.app.focus_set()
            self.app.pause()

class ResetButton(ButtonPanel):
    def __init__(self, app, index) -> None:
        super().__init__(app, index)
    def on(self):
        self.app.focus_set()
        self.app.softReset()
        self.app.event_generate("<<Stop>>", when="tail")


class Panel:
    def __init__(self, app):
        self.app = app
        self.period = Utils.getFloat("Panel", "period", 0.1)
        self.mapper = {"stepselector":StepSelector, "rapidselector":RapidSelector,
                "feedselector":FeedSelector, "startbutton":StartButton,
                "pausebutton":PauseButton, "startpausebutton":StartPauseButton,
                "resetbutton": ResetButton, "button":ButtonPanel}
        self.members = []
        self.members += [Jog(app)]
        index = 0
        while 1:
            name = Utils.getStr("Panel", "selector{}".format(index), "").lower()
            if name not in self.mapper.keys():
                break
            self.members += [self.mapper[name](self.app, index)]
            index += 1

        index = 0
        while 1:
            name = Utils.getStr("Panel", "button{}".format(index), "").lower()
            if name not in self.mapper.keys():
                break
            self.members += [self.mapper[name](self.app, index)]
            index += 1

        self.active = Utils.getBool("CNC", "panel", False)
        self.lastCheck = time.time()
        self.mtx = threading.Lock()
        self.mtx.acquire()
        self.th = threading.Thread(target=self.updateTask)
        self.th.start()

    def updateTask(self):
        while self.mtx.locked() and self.app is not None:
            time.sleep(self.period)
            self.update()

    def stopTask(self):
        self.mtx.release()

    def update(self):
        if not self.active:
            return
        t = time.time()
        if t > self.lastCheck + self.period:
            for member in self.members:
                if not member.active:
                    continue
                member.check()

            self.lastCheck = t
