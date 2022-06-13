import threading
import time
import wiringpi as wp
import Utils

from CNC import CNC

wp.wiringPiSetup()

class Member:
    def __init__(self, pins, debounce, callback):
        self.pins = pins
        self.debounce = debounce
        self.callback = callback
        self.mutex = threading.Lock()
        for pin in pins:
            if pin < 0: continue
            wp.pinMode(pin, wp.INPUT)
            wp.pullUpDnControl(pin, wp.PUD_DOWN)

        self.lastTime = time.time()

    def read(self, pin):
        if pin < 0:
            return (CNC.vars["inputs"] & (2 ** (-pin - 1))) > 0
        return wp.digitalRead(pin)

    def waitDebounce(self):
        pinValues = [self.read(pin) for pin in self.pins]
        time.sleep(self.debounce)
        pinValuesDebounced = [self.read(pin) for pin in self.pins]

        pinValues = [(a & b) for (a, b) in zip(pinValues, pinValuesDebounced)]

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

class Panel:
    def __init__(self, app):
        self.period = 0.05
        pins = []
        self.jogActive = Utils.getBool("Panel", "jogPanel", False) and not Utils.getBool("Panel", "jogKeyboard", True)
        if self.jogActive:
            pins = getArrayIntFromUtils("Panel", ["X", "Xdir", "B","Bdir", "Z", "Zdir"])
        self.memberJog = Member(pins, 0.05, self.jog)
        self.axisMap = {0: "X", 1: "B", 2: "Z"}
        self.directionMap = {0: "Up", 1: "Down"}
        self.JOGMOTION = 0
        self.JOGSTOP = 1
        self.jogLastAction = self.JOGMOTION

        pins = []
        self.steps = [0]
        self.velocitys = [0]
        self.selectorActive = Utils.getBool("Panel", "selectorPanel", False)
        if self.selectorActive:
            selPins = Utils.getInt("Panel", "selectorPins",0)
            pins = getArrayIntFromUtils("Panel", 
                                ["selector{}".format(i) for i in range(0,selPins)])
            selSteps = Utils.getInt("Panel", "selectorSteps",0)
            self.steps = getArrayFloatFromUtils("Panel", 
                                ["selectorStep{}".format(i) for i in range(0,selSteps)])
            selVels = Utils.getInt("Panel", "selectorVels",0)
            self.velocitys = getArrayFloatFromUtils("Panel", 
                                ["selectorVel{}".format(i) for i in range(0,selVels)])
        self.selectorType = Utils.getBool("Panel", "selectorTypeBinary", False)
        self.memberSelector = Member(pins, 0.05, self.selector)
        self.currentStep = self.steps[0]
        self.currentVelocity = self.velocitys[0]

        pins = []
        self.spPanelActive = Utils.getBool("Panel", "spPanel", False)
        if self.spPanelActive:
            buttons = Utils.getInt("Panel", "spButtons", 0)
            if buttons==1:
                pins = [Utils.getInt("Panel", "spButton", -20)]
            else: pins = getArrayIntFromUtils("Panel", ["startButton", "pauseButton"])
        self.memberStartPause = Member(pins, 0.1, self.startPause)
        self.lastStartPauseState = [0]

        pins = []
        self.clampActive = Utils.getBool("Panel", "clampPanel", False)
        if self.clampActive:
            pins = [Utils.getInt("Panel", "clampButton", -20)]
        self.memberClamp = Member(pins, 0.1, self.clamp)
        self.lastClampState = None

        self.active = Utils.getBool("CNC", "panel", False)
        self.app = app
        self.lastCheck = time.time()

    def jog(self, pinValues):
        if self.app.running:
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
            mutex.acquire(blocking=True, timeout=2)
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
                mutex.acquire(blocking=True, timeout=2)
                self.app.jogMutex = None
                return
    def clamp(self, pinValues):
        if pinValues == self.lastClampState:
            return
        self.lastClampState = pinValues
        if max(pinValues) == 0:
            return
        self.app.event_generate("<<ClampToggle>>", when="tail")

    def selector(self, selector: list):
        index = 0
        if not self.selectorType:
            for id, w in enumerate(selector):
                if w == 1:
                    index = id
        else: 
            for id, w in enumerate(selector):
                if w == 1:
                    index += 2 ** id
        step = self.steps[index]
        velocity = self.velocitys[index]
        if step != self.currentStep or velocity != self.currentVelocity:
            self.currentStep = step
            self.currentVelocity = velocity
            self.app.event_generate("<<AdjustSelector>>", when="tail")

    def startPause(self, state):
        if state == self.lastStartPauseState:
            return
        self.lastStartPauseState = state
        if max(state) == 0:
            return
        if CNC.vars["state"] == "Idle" and not self.app.running:
            self.app.event_generate("<<Run>>", when="tail")
        else:
            self.app.pause()

    def update(self):
        if not self.active:
            return
        t = time.time()
        if t > self.lastCheck + self.period:
            if self.jogActive:
                self.memberJog.check()
            if self.spPanelActive:
                self.memberStartPause.check()
            if self.selectorActive:
                self.memberSelector.check()
            if self.clampActive:
                self.memberClamp.check()
            self.lastCheck = t
