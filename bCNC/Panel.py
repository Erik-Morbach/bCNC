import abc
import threading
import time
import Utils
import io

from CNC import CNC

def is_raspberrypi():
    try:
        with io.open('/sys/firmware/devicetree/base/model', 'r') as m:
            if 'raspberry pi' in m.read().lower(): 
                return True
    except Exception:
        pass
    return False

if is_raspberrypi():
    print("Is a Pi")
    import wiringpi as wp
    wp.wiringPiSetupGpio()
else:
    print("Not a Pi")
    class A:
        INPUT = 0
        PUD_DOWN = 1
        PUD_OFF = 2
        def pinMode(self, *args):
            pass
        def pullUpDnControl(self, *args):
            pass
        def digitalRead(self, *args):
            return 0
    wp = A()

class Member:
    def __init__(self, pins, inversion, debounce, callback, active):
        print("Member:", end='')
        self.pins = pins
        self.debounce = debounce
        self.callback = callback
        self.mutex = threading.Lock()
        self.active = active
        for pin in pins:
            print(" " + str(pin), end='')
            if pin < 0: continue
            wp.pinMode(pin, wp.INPUT)
            wp.pullUpDnControl(pin, wp.PUD_DOWN)
        print()

        self.inversion = inversion
        self.lastTime = time.time()

    def read(self, pin):
        if pin < 0:
            return (CNC.vars["inputs"] & (2 ** (-pin - 1))) > 0
        return wp.digitalRead(pin)

    def waitDebounce(self):
        haveErro = False
        debounceQnt = 100
        pinValues = [0]*len(self.pins)
        for _ in range(debounceQnt):
            time.sleep(self.debounce/debounceQnt)
            pinValuesDebounced = [self.read(pin) for pin in self.pins]
            for i in range(len(pinValues)):
                pinValues[i] += pinValuesDebounced[i]

        for i in range(len(pinValues)):
            if pinValues[i] > 0 and pinValues[i] < debounceQnt:
                haveErro = True
                break
            pinValues[i] = 1 if pinValues[i]==debounceQnt else 0
            if self.inversion & (2**i):
                pinValues[i] = not pinValues[i]
        if not haveErro:
            self.callback(pinValues)
        self.mutex.release()

    def check(self):
        if self.mutex.locked():
            return
        if time.time() < self.lastTime + self.debounce:
            return
        self.lastTime = time.time()
        self.mutex.acquire()
        threading.Thread(target=self.waitDebounce).start()

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
    def __init__(self, app, pins, inversion, debounce, callback, active):
        super().__init__(pins, inversion, debounce, callback, active)
        self.app = app

    @abc.abstractmethod
    def load_pins(self):
        pass
    @abc.abstractmethod
    def callback(self):
        pass

class Jog(MemberImpl):
    JOGMOTION = 0
    JOGSTOP = 1
    def __init__(self, app):
        self.active = Utils.getBool("Jog", "panel", False) and not Utils.getBool("Jog", "keyboard", True)

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

        pins, inversion = self.load_pins()
        self.lastPinValues = []

        print("JOG", end=' ')
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
                mutex = threading.Lock()
                mutex.acquire()
                self.app.jogMutex = mutex
                self.app.focus_set()
                self.app.event_generate("<<"+con+">>", when="tail")
                self.jogLastAction = self.JOGMOTION
                mutex.acquire(blocking=True, timeout=0.5)
                self.app.jogMutex = None
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
        mutex = threading.Lock()
        mutex.acquire()
        self.app.jogMutex = mutex
        self.app.focus_set()
        self.app.jogData = data
        self.app.event_generate("<<JOG>>", when="tail")
        self.jogLastAction = self.JOGMOTION
        mutex.acquire(blocking=True, timeout=0.5)
        self.app.jogMutex = None

    def callback(self, pinValues):
        if self.app.running.running or CNC.vars["state"] == "Home" or not CNC.vars["JogActive"]:
            return
        shouldStop = False
        if len(self.lastPinValues) == len(pinValues):
            for (a,b) in zip(self.lastPinValues, pinValues):
                if a!=b:
                    shouldStop = True
        self.lastPinValues = pinValues
        if shouldStop and self.jogLastAction != self.JOGSTOP:
            mutex = threading.Lock()
            mutex.acquire()
            self.app.jogMutex = mutex
            self.app.focus_set()
            self.app.event_generate("<<JogStop>>", when="tail")
            self.jogLastAction = self.JOGSTOP
            mutex.acquire(blocking=True, timeout=0.5)
            self.app.jogMutex = None
            return
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

        print(self.selectorName, end= ' ')
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
        print("Button{}".format(index), end=' ')
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

class ClampButton(ButtonPanel):
    def __init__(self, app, index) -> None:
         super().__init__(app, index)
    def on(self):
        self.app.executeCommand("ClampToggle")

class SafetyDoorButton(ButtonPanel):
    def __init__(self, app, index) -> None:
         super().__init__(app, index)
    def on(self):
        CNC.vars["SafeDoor"] = 1
        self.app.focus_set()
        self.app.event_generate("<<Stop>>", when="tail")
    def off(self):
        CNC.vars["SafeDoor"] = 0

class BarEndButton(ButtonPanel):
    def __init__(self, app, index) -> None:
        super().__init__(app,index)
    def on(self):
        CNC.vars["barEnd"] = 1
        self.app.feedHold()
    def off(self):
        CNC.vars["barEnd"] = 0

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
                "clampbutton":ClampButton, "safetydoorbutton":SafetyDoorButton,
                "barendbutton":BarEndButton, "resetbutton": ResetButton,
                "button":ButtonPanel}
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
