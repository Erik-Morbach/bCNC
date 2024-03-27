import abc
import threading
import time
import Utils
import io
import logging

from CNC import CNC

import tkinter
import gpiozero
import smbus2

from mttkinter import *


def is_raspberrypi():
    try:
        with io.open('/sys/firmware/devicetree/base/model', 'r') as m:
            if 'raspberry pi' in m.read().lower():
                return True
    except Exception:
        pass
    return False


logPanel = logging.getLogger("Panel")
logPanel.setLevel(logging.INFO)


class gpio:
    def __init__(self) -> None:
        self.obj = {}

    def setup(self, pin):
        try:
            self.obj[pin] = gpiozero.Button(pin, pull_up=False)
        except BaseException:
            self.obj[pin] = None

    def read(self, pin):
        if pin not in self.obj.keys() or self.obj[pin] is None:
            return 0
        return self.obj[pin].is_pressed


class i2c:
    def __init__(self) -> None:
        self.obj = {}
        self.bus = smbus2.SMBus(1)
        self.pollPeriod = {}
        self.lastTime = {}

    @staticmethod
    def getId(device, address):
        return str(device) + str(address)

    def register(self, devId):
        if devId not in self.obj.keys():
            self.obj[devId] = 0
        if devId not in self.lastTime.keys():
            self.lastTime[devId] = 0
        if devId not in self.pollPeriod.keys():
            self.pollPeriod[devId] = 0

    def isRegistered(self, devId):
        return devId in self.obj.keys()

    def get(self, devId):
        return (self.obj[devId], self.lastTime[devId], self.pollPeriod[devId])

    def set(self, devId, value, lastTime):
        self.obj[devId] = value
        self.lastTime[devId] = lastTime

    def setup(self, device, address, pollPeriod):
        devId = i2c.getId(device, address)
        self.register(devId)

        if pollPeriod != -1:
            self.pollPeriod[i2c.getId(device, address)] = pollPeriod

    def read(self, dev, addr):
        devId = i2c.getId(dev, addr)
        if not self.isRegistered(devId):
            self.register(devId)

        lastValue, lastTime, pollPeriod = self.get(devId)

        if time.time() - lastTime < pollPeriod:
            return lastValue
        value = self.bus.read_byte_data(dev, addr)
        self.set(devId, value, time.time())
        return value


class Pins:
    def __init__(self) -> None:
        self.gpio = gpio()
        self.i2c = i2c()
        self.counter = 0
        self.mapper = {}

    def setupGpio(self, pin):
        id = self.counter
        self.counter += 1
        self.gpio.setup(pin)
        self.mapper[id] = (0, pin)
        return id

    def setupI2c(self, device, address, bit, pollPeriod=-1):
        id = self.counter
        self.counter += 1
        self.i2c.setup(device, address, pollPeriod)
        self.mapper[id] = (1, device, address, bit)
        return id

    def setupExternal(self, pin):
        id = self.counter
        self.counter += 1
        self.mapper[id] = (2, pin)
        return id

    def read(self, id):
        st = self.mapper[id]
        if st[0] == 0:
            return self.gpio.read(st[1])
        if st[0] == 1:
            value = self.i2c.read(st[1], st[2])
            if st[3] > -1:
                value = value & (1 << st[3])
            return 1 if value else 0
        if st[0] == 2:
            value = CNC.vars["inputs"] & (1 << st[1])
            return 1 if value else 0


PINS = Pins()

if is_raspberrypi():
    logPanel.info("Is running on a Pi")
else:
    logPanel.info("Is running on a PC")


class Member:
    def __init__(self):
        self.memberName = "Member"
        self.mutex = threading.Lock()
        self.lastTime = time.time()
        self.lastValues = []
        self.th_mtx = threading.Lock()
        self.th = threading.Thread(target=self.threadMethod)
        self.pins = []
        self.debounce = 0
        self.active = False

    def setup(self, pins, inversion, debounce, callback, active):
        infoStr = "Member: "
        self.pins = pins
        self.lastValues = [0]*len(pins)
        self.debounce = debounce
        self.callback = callback
        self.active = active
        for (index, pin) in enumerate(pins):
            infoStr += " " + str(pin)
            id = 0
            if pin[0] == "g":
                pinValue = int(pin[1:])
                id = PINS.setupGpio(pinValue)
            if pin[0] == "e":
                pinValue = int(pin[1:])
                id = PINS.setupExternal(pinValue)
            if pin[0] == "i":
                pollPeriod = -1
                if '(' in pin:
                    idxB = pin.find('(')+1
                    idxE = pin.find(')')
                    pollPeriod = float(pin[idxB:idxE])
                    pin = pin[:idxB-1]

                d, a = pin[1:].split(":")
                a, b = a.split('.')
                dev = int(d, 16)
                addr = int(a, 16)
                bit = int(b)
                id = PINS.setupI2c(dev, addr, bit, pollPeriod)
            self.pins[index] = id
        logPanel.info(infoStr)

        self.inversion = inversion

    def start(self):
        if self.th_mtx.locked():
            return
        self.th_mtx.acquire()
        self.th.start()

    def stop(self):
        if not self.th_mtx.locked():
            return
        self.th_mtx.release()

    def threadMethod(self):
        debouncer_qnt = 10
        debouncer_period = self.debounce/debouncer_qnt
        window = [[0]*len(self.pins) for _ in range(debouncer_qnt)]
        index = 0
        current_sum = [0]*len(self.pins)
        logPanel.info(self.memberName + " thread begin")
        while self.th_mtx.locked():
            time.sleep(debouncer_period)
            pinValues = [PINS.read(pin) for pin in self.pins]
            current_sum = [(a - b)
                           for (a, b) in zip(current_sum, window[index])]
            window[index] = pinValues
            current_sum = [(a + b)
                           for (a, b) in zip(current_sum, window[index])]

            index += 1
            index %= len(window)

            haveErro = any([(a != 0 and a != debouncer_qnt)
                           for a in current_sum])

            values = []
            for (id, w) in enumerate(current_sum):
                values += [1 if w == debouncer_qnt else 0]
                values[-1] ^= (1 if (self.inversion & (1 << id)) else 0)

            if not haveErro:
                self.lastValues[:] = values[:]
                self.callback(values)
        logPanel.info(self.memberName + " thread end")

    def callback(self, pinValues):
        return

    def read(self, pin):
        return PINS.read(pin)


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


class MemberImpl(Member):
    def __init__(self, app):
        super().__init__()
        self.app = app

    @abc.abstractmethod
    def load_pins(self):
        return [], 0


class Jog(MemberImpl):
    JOGMOTION = 0
    JOGSTOP = 1

    def __init__(self, app):
        super().__init__(app)
        self.memberName = "Jog"
        self.active = Utils.getBool("Jog", "panel", False)

        self.type = Utils.getBool("Jog", "directionMode", True)
        # directionMode:
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
            self.directMappings += [w+"Up", w+"Down"]

        self.jogLastAction = self.JOGMOTION
        debounce = Utils.getFloat("Jog", "debounce", 0.05)
        self.plannerLimit = Utils.getInt("Jog", "planner", 90)

        pins, inversion = self.load_pins()
        self.lastPinValues = []

        logPanel.info("Jog Member: ")
        self.setup(pins, inversion, debounce, self.callback, self.active)

    def load_pins(self):
        pins = []
        inversion = 0
        arr = []
        if self.type:
            for w in self.axisMap:
                arr += [w, w+"dir"]
        else:
            arr = self.directMappings
        pins = getArrayFromUtils("Jog", arr, Utils.getStr, "e20")
        inversion = Utils.getInt("Jog", "inversion", 0)
        return pins, inversion

    def directionMode(self, pinValues):
        axis = []
        direction = []
        for i in range(0, len(pinValues)):
            if i % 2 == 0:
                axis += [pinValues[i]]
            else:
                direction += [pinValues[i]]
        for id, (axe, dire) in enumerate(zip(axis, direction)):
            if axe == 1:
                con = self.axisMap[id] + self.directionMap[dire]
                code = self.app.jogController.mapKeyToCode[con][0]
                codeWrapper = tkinter.EventType.KeyPress, code
                self.app.jogController.jogEvent(simulatedData=codeWrapper)
                return

    def directMode(self, pinValues):
        data = ""
        for id, val in enumerate(pinValues):
            if val == 1:
                con = self.directMappings[id]
                if len(data) > 2:
                    if data[-2] == con[0]:
                        continue
                data += con[0]
                data += '+' if con[1:] == "Up" else '-'
        if len(data) == 0:
            return
        for i in range(0, len(data), 2):
            key = data[i:i+2]
            code = self.app.jogController.mapKeyToCode[key][0]
            codeWrapper = tkinter.EventType.KeyPress, code
            self.app.jogController.jogEvent(simulatedData=codeWrapper)

    def callback(self, pinValues):
        shouldStop = False
        if len(self.lastPinValues) == len(pinValues):
            for (a, b) in zip(self.lastPinValues, pinValues):
                if a != b:
                    shouldStop = True
        self.lastPinValues = pinValues
        if shouldStop:
            return
        if self.type:
            self.directionMode(pinValues)
        else:
            self.directMode(pinValues)


class Selector(MemberImpl):
    def __init__(self, memberName, app, index, onChange) -> None:
        super().__init__(app)
        self.onChange = onChange
        self.selectorIndex = index
        self.memberName = memberName  # "Selector{}".format(index)
        self.utilsName = self.memberName
        self.active = Utils.getBool(self.utilsName, "panel", False)
        debounce = Utils.getFloat(self.utilsName, "debounce", 0.1)
        self.selectorBinaryType = Utils.getBool(
            self.utilsName, "binary", False)
        self.grayCodeActive = Utils.getBool(self.utilsName, "gray", False)

        def binary(index, id): return index + (2**id)
        def direct(index, id): return id
        self.typeFunction = binary if self.selectorBinaryType else direct

        self.variableBegin = Utils.getFloat(self.utilsName, "begin", -1)
        self.variableEnd = Utils.getFloat(self.utilsName, "end", -1)
        self.variableOptions = getArrayWhileExists(
            self.utilsName, "v", Utils.getFloat, 0)

        pins, inversion = self.load_pins()

        self.useBeginEnd = self.variableBegin != -1
        self.resolution = len(pins)
        if self.selectorBinaryType:
            self.resolution = 2**self.resolution-1
        self.resolution = Utils.getInt(
            self.utilsName, "resolution", self.resolution)

        logPanel.info(self.memberName + " Member: ")
        if self.useBeginEnd:
            self.currentVar = self.variableBegin
        else:
            self.currentVar = self.variableOptions[0]
        self.setup(pins, inversion, debounce, self.callback, self.active)

    def load_pins(self):
        pins = getArrayWhileExists(self.utilsName, "pin", Utils.getStr, "e20")
        inversion = Utils.getInt(self.utilsName, "inversion", 0)
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

    def callback(self, pinValues: list):
        index = self.calculateIndex(pinValues)
        var = 0
        if self.useBeginEnd:
            var = (self.variableEnd - self.variableBegin)/self.resolution
            var = var*index + self.variableBegin
        else:
            var = self.variableOptions[index]
        if var != self.currentVar:
            self.currentVar = var
            self.onChange()
        return


class StepSelector(Selector):
    def __init__(self, app, index) -> None:
        self.memberName = "Step Selector"
        super().__init__(self.memberName, app, index, self.onChange)

    def onChange(self):
        self.app.control.setStep(self.currentVar)


class FeedSelector(Selector):
    def __init__(self, app, index, names=["Feed"]) -> None:
        self.memberName = "Feed Selector"
        super().__init__(self.memberName, app, index, self.onChange)
        self.names = names

    def change(self, name, var):
        self.app.gstate.setOverride(name, var)

    def onChange(self):
        for w in self.names:
            self.change(w, self.currentVar)
        self.app.mcontrol.overrideSet()


class RapidSelector(Selector):
    def __init__(self, app, index, names=["Rapid"]) -> None:
        self.memberName = "Rapid Selector"
        super().__init__(self.memberName, app, index, self.onChange)
        self.names = names

    def change(self, name, var):
        self.app.gstate.setOverride(name, var)

    def onChange(self):
        for w in self.names:
            self.change(w, self.currentVar)
        self.app.mcontrol.overrideSet()


class ButtonPanel(MemberImpl):
    def __init__(self, app, index) -> None:
        super().__init__(app)
        self.memberName = "Button{}".format(index)
        self.utilsName = self.memberName
        self.description = Utils.getStr(self.utilsName, "name", self.utilsName)
        self.active = Utils.getBool(self.utilsName, "panel", False)
        debounce = Utils.getFloat(self.utilsName, "debounce", 0.5)
        pins, inversion = self.load_pins()
        logPanel.info("Button%d Member:" % (index))
        self.lastState = [0]
        self.onOnExecute = Utils.getStr(self.utilsName, "on", "")
        self.onOffExecute = Utils.getStr(self.utilsName, "off", "")
        self.setup(pins, inversion, debounce, self.callback, self.active)

    def load_pins(self):
        pins = [Utils.getStr(self.utilsName, "pin", "e20")]
        inversion = Utils.getInt(self.utilsName, "inversion", 0)
        return pins, inversion

    def callback(self, pinValues: list):
        state = 0
        if len(pinValues):
            state = pinValues[0]
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
        self.memberName = "Start Button"

    def on(self):
        if CNC.vars["state"] == "Idle" and not self.app.running.value and CNC.vars["execution"]:
            self.app.focus_set()
            self.app.event_generate("<<Run>>", when="tail")
        elif "hold" in CNC.vars["state"].lower():
            self.app.resume()


class PauseButton(ButtonPanel):
    def __init__(self, app, index) -> None:
        super().__init__(app, index)
        self.memberName = "Pause Button"
        self.lastState = 0

    def on(self):
        self.app.feedHold()


class StartPauseButton(ButtonPanel):
    def __init__(self, app, index) -> None:
        super().__init__(app, index)
        self.memberName = "Start Pause Button"

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
        self.memberName = "Reset Button"

    def on(self):
        self.app.focus_set()
        self.app.softReset()
        self.app.event_generate("<<Stop>>", when="tail")


class Panel:
    def __init__(self, app):
        self.app = app
        self.period = Utils.getFloat("Panel", "period", 0.1)
        self.mapper = {"stepselector": StepSelector, "rapidselector": RapidSelector,
                       "feedselector": FeedSelector, "startbutton": StartButton,
                       "pausebutton": PauseButton, "startpausebutton": StartPauseButton,
                       "resetbutton": ResetButton, "button": ButtonPanel}
        self.members = []
        self.members += [Jog(app)]
        index = 0
        while 1:
            name = Utils.getStr(
                "Panel", "selector{}".format(index), "").lower()
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

        if self.active:
            for m in self.members:
                if m.active:
                    m.start()

    def stopTask(self):
        for m in self.members:
            m.stop()
