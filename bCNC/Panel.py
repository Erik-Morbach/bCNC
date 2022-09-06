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
	wp.wiringPiSetup()
else:
	print("Not a Pi")
	class A:
		INPUT = 0
		PUD_DOWN = 1
		def pinMode(self, *args):
			pass
		def pullUpDnControl(self, *args):
			pass
		def digitalRead(self, *args):
			return 0
	wp = A()

class Member:
    def __init__(self, pins, inversion, debounce, callback, active):
        self.pins = pins
        self.debounce = debounce
        self.callback = callback
        self.mutex = threading.Lock()
        self.active = active
        for pin in pins:
            if pin < 0: continue
            wp.pinMode(pin, wp.INPUT)
            wp.pullUpDnControl(pin, wp.PUD_DOWN)

        self.inversion = inversion
        self.lastTime = time.time()

    def read(self, pin):
        if pin < 0:
            return (CNC.vars["inputs"] & (2 ** (-pin - 1))) > 0
        return wp.digitalRead(pin)

    def waitDebounce(self):
        pinValues = [self.read(pin) for pin in self.pins]
        for _ in range(10):
            time.sleep(self.debounce/10)
            pinValuesDebounced = [self.read(pin) for pin in self.pins]
            for i in range(len(pinValues)):
                pinValues[i] += pinValuesDebounced[i]

        for i in range(len(pinValues)):
            pinValues[i] = 1 if pinValues[i]>=5 else 0
            if self.inversion & (2**i):
                pinValues[i] = not pinValues[i]
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

def getArrayIntFromUtils(section, array):
    values = []
    for w in array:
        values += [Utils.getInt(section, w, -20)]
    return values

def getArrayFloatFromUtils(section, array):
    values = []
    for w in array:
        values += [Utils.getFloat(section, w, 0)]
    return values

class MemberImpl(abc.ABC):
    def __init__(self,app) -> None:
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
        super().__init__(app)
        self.jogActive = Utils.getBool("Jog", "panel", False) and not Utils.getBool("Jog", "keyboard", True)

        self.axisMap = "XYZABC"
        self.directionMap = {0: "Up", 1: "Down"}
        self.jogLastAction = self.JOGMOTION
        debounce = Utils.getFloat("Jog", "debounce", 0.05)

        pins, inversion = self.load_pins()

        self.member = Member(pins, inversion, debounce, self.callback, self.jogActive)

    def load_pins(self):
        pins = []
        inversion = 0
        arr = []
        for w in self.axisMap:
            arr += [w, w+"dir"]
        pins = getArrayIntFromUtils("Jog", arr)
        inversion = Utils.getInt("Jog", "inversion", 0)
        return pins, inversion

    def callback(self, pinValues):
        if self.app.running or CNC.vars["state"] == "Home":
            return
        axis = []
        direction = []
        for i in range(0,len(pinValues)):
            if i % 2 == 0: axis += [pinValues[i]]
            else: direction += [pinValues[i]]
        if max(axis) == 0 and self.jogLastAction != self.JOGSTOP:
            mutex = threading.Lock()
            mutex.acquire()
            self.app.jogMutex = mutex
            self.app.focus_set()
            self.app.event_generate("<<JogStop>>", when="tail")
            self.jogLastAction = self.JOGSTOP
            mutex.acquire(blocking=True, timeout=0.5)
            self.app.jogMutex = None
            return
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

class Selector(MemberImpl):
    def __init__(self, app, index, onChange) -> None:
        super().__init__(app)
        self.onChange = onChange
        self.selectorIndex = index
        self.selectorName = "Selector{}".format(index)
        self.selectorActive = Utils.getBool(self.selectorName, "panel", False)
        debounce = Utils.getFloat(self.selectorName, "debounce", 0.1)
        self.selectorType = Utils.getBool(self.selectorName, "binary", False)

        binary =  lambda index, id: index + (2**id)
        direct = lambda index, id: id
        self.typeFunction = binary if self.selectorType else direct

        pinsLen = Utils.getInt(self.selectorName, "pinsLen", 0)
        self.variableOptions = getArrayFloatFromUtils(self.selectorName,
                            ["v{}".format(i) for i in range(0,pinsLen)])

        pins, inversion = self.load_pins()

        self.memberSelector = Member(pins, inversion, debounce, self.callback, self.selectorActive)
        self.currentVar = self.variableOptions[0]

    def load_pins(self):
        selPins = Utils.getInt("Selector", "pins",0)
        pins = getArrayIntFromUtils("Selector", 
                            ["pin{}".format(i) for i in range(0,selPins)])
        inversion = Utils.getInt("Selector", "inversion", 0)
        return pins, inversion

    def calculateIndex(self, selector: list):
        index = 0
        for id, w in enumerate(selector):
            if w == 1:
                index = self.typeFunction(index, id)
        return index

    def callback(self, selector: list):
        index = self.calculateIndex(selector)
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
    def __init__(self, app, index, names = ["Feed","Rapid"]) -> None:
         super().__init__(app, index, self.onChange)
         self.names = names
    def change(self, name, var):
        self.app.gstate.overrideCombo.set(name)
        self.app.gstate.override.set(var)
        self.app.gstate.overrideChange()
    def onChange(self):
        for w in self.names:
            self.change(w, self.currentVar)

class ButtonPanel(MemberImpl):
    def __init__(self, app, index) -> None:
        super().__init__(app)
        self.panelName = "Button{}".format(index)
        self.active = Utils.getBool(self.panelName, "panel", False)
        debounce = Utils.getFloat(self.panelName, "debounce", 0.5)
        pins, inversion = self.load_pins()
        self.member = Member(pins, inversion, debounce, self.callback, self.active)
        self.lastState = [0]

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
        pass
    def off(self):
        pass


class StartButton(ButtonPanel):
    def __init__(self, app, index) -> None:
         super().__init__(app, index)
    def on(self):
        if CNC.vars["state"] == "Idle" and not self.app.running:
            self.app.event_generate("<<Run>>", when="tail")
        elif CNC.vars["state"] == "Hold":
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
        if CNC.vars["state"] == "Idle" and not self.app.running:
            self.app.event_generate("<<Run>>", when="tail")
        else:
            self.app.focus_set()
            self.app.pause()

class ClampButton(ButtonPanel):
    def __init__(self, app, index) -> None:
         super().__init__(app, index)
    def on(self):
        self.app.event_generate("<<ClampToggle>>", when="tail")

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
        self.mapper = {"stepselector":StepSelector,
                "feedselector":FeedSelector, "startbutton":StartButton,
                "pausebutton":PauseButton, "startpausebutton":StartPauseButton,
                "clampbutton":ClampButton, "safetydoorbutton":SafetyDoorButton,
                "barendbutton":BarEndButton, "resetbutton": ResetButton}
        self.members = []
        self.selectorCounter = 0
        self.buttonCounter = 0
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
