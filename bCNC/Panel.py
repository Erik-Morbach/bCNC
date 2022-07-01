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

class Panel:
    def __init__(self, app):
        self.period = Utils.getFloat("Panel", "period", 0.1)
        self.members = []
        pins = []
        inversion = 0
        self.jogActive = Utils.getBool("Jog", "panel", False) and not Utils.getBool("Jog", "keyboard", True)
        debounce = Utils.getFloat("Jog", "debounce", 0.05)
        if self.jogActive:
            pins = getArrayIntFromUtils("Jog", ["X", "Xdir", "B","Bdir", "Z", "Zdir"])
            inversion = Utils.getInt("Jog", "inversion", 0)
        self.memberJog = Member(pins, inversion, debounce, self.jog, self.jogActive)
        self.axisMap = {0: "X", 1: "B", 2: "Z"}
        self.directionMap = {0: "Up", 1: "Down"}
        self.JOGMOTION = 0
        self.JOGSTOP = 1
        self.jogLastAction = self.JOGMOTION
        self.members += [self.memberJog]

        pins = []
        inversion = 0
        self.steps = [0]
        self.velocitys = [0]
        self.selectorActive = Utils.getBool("Selector", "panel", False)
        debounce = Utils.getFloat("Selector", "debounce", 0.1)
        self.selectorType = Utils.getBool("Selector", "binary", False)
        if self.selectorActive:
            selPins = Utils.getInt("Selector", "pins",0)
            pins = getArrayIntFromUtils("Selector", 
                                ["pin{}".format(i) for i in range(0,selPins)])
            inversion = Utils.getInt("Selector", "inversion", 0)

            selSteps = Utils.getInt("Selector", "steps",0)
            self.steps = getArrayFloatFromUtils("Selector", 
                                ["step{}".format(i) for i in range(0,selSteps)])
            selVels = Utils.getInt("Selector", "vels",0)
            self.velocitys = getArrayFloatFromUtils("Selector", 
                                ["vel{}".format(i) for i in range(0,selVels)])
        self.memberSelector = Member(pins, inversion, debounce, self.selector, self.selectorActive)
        self.currentStep = self.steps[0]
        self.currentVelocity = self.velocitys[0]
        self.members += [self.memberSelector]

        pins = []
        inversion = 0
        self.spPanelActive = Utils.getBool("StartPause", "panel", False)
        debounce = Utils.getFloat("StartPause", "debounce", 0.5)
        if self.spPanelActive:
            buttons = Utils.getInt("StartPause", "pins", 0)
            if buttons==1:
                pins = [Utils.getInt("StartPause", "pin", -20)]
            else: pins = getArrayIntFromUtils("StartPause", ["start", "pause"])
            inversion = Utils.getInt("StartPause", "inversion", 0)
        self.memberStartPause = Member(pins, inversion, debounce, self.startPause, self.spPanelActive)
        self.lastStartPauseState = [0]
        self.members += [self.memberStartPause]

        pins = []
        inversion = 0
        self.clampActive = Utils.getBool("Clamp", "panel", False)
        debounce = Utils.getFloat("Clamp", "debounce", 0.15)
        if self.clampActive:
            pins = [Utils.getInt("Clamp", "pin", -20)]
            inversion = Utils.getInt("Clamp", "inversion", 0)
        self.memberClamp = Member(pins, inversion, debounce, self.clamp, self.clampActive)
        self.lastClampState = None
        self.members += [self.memberClamp]

        pins = []
        inversion = 0
        self.safetyDoorActive = Utils.getBool("SafetyDoor", "panel", False)
        debounce = Utils.getFloat("SafetyDoor", "debounce", 0.5)
        if self.safetyDoorActive:
            pins = [Utils.getInt("SafetyDoor", "pin", -20)]
            inversion = Utils.getInt("SafetyDoor", "inversion", 0)
        self.memberSafetyDoor = Member(pins, inversion, debounce, self.safetyDoor, self.safetyDoorActive)
        self.safetyDoorLastState = 0
        self.members += [self.memberSafetyDoor]

        pins = []
        inversion = 0
        self.barEndActive = Utils.getBool("BarEnd", "panel", False)
        debounce = Utils.getFloat("BarEnd", "debounce", 0.5)
        if self.barEndActive:
            pins = [Utils.getInt("BarEnd", "pin", -20)]
            inversion = Utils.getInt("BarEnd", "inversion", 0)
        self.memberBarEnd = Member(pins, inversion, debounce, self.barEnd, self.barEndActive)
        self.members += [self.memberBarEnd]

        self.active = Utils.getBool("CNC", "panel", False)
        self.app = app
        self.lastCheck = time.time()

    def jog(self, pinValues):
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
    def clamp(self, pinValues):
        if pinValues == self.lastClampState:
            return
        self.lastClampState = pinValues
        if max(pinValues) == 0:
            return
        self.app.focus_set()
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
        indexProp = index / (2**len(selector) if self.selectorType else len(selector))
        stepIndex = int(indexProp * len(self.steps))
        velocityIndex = int(indexProp * len(self.velocitys))
        step = self.steps[stepIndex]
        velocity = self.velocitys[velocityIndex]
        if step != self.currentStep or velocity != self.currentVelocity:
            self.currentStep = step
            self.currentVelocity = velocity
            self.app.focus_set()
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
            self.app.focus_set()
            self.app.pause()

    def safetyDoor(self, state):
        CNC.vars["SafeDoor"] = state[0]
        if state[0] == self.safetyDoorLastState:
            return
        self.safetyDoorLastState = state[0]
        if state[0]:
            self.app.focus_set()
            self.app.event_generate("<<Stop>>", when="tail")

    def barEnd(self, state):
        CNC.vars["barEnd"] = state[0]

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
