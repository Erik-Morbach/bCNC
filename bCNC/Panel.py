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
            wp.pinMode(pin, wp.INPUT)
            wp.pullUpDnControl(pin, wp.PUD_DOWN)
        self.lastTime = time.time()

    def waitDebounce(self):
        pinValues = [wp.digitalRead(pin) for pin in self.pins]
        time.sleep(self.debounce)
        pinValuesDebounced = [wp.digitalRead(pin) for pin in self.pins]

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

class Panel:
    def __init__(self, app, keys):
        self.period = 0.05
        self.memberJog = Member([2, 3, 4, 21], 0.05, self.jog)
        self.axisMap = {0: "X", 1: "B", 2: "Z"}
        self.directionMap = {0: "Up", 1: "Down"}
        self.JOGMOTION = 0
        self.JOGSTOP = 1
        self.jogLastAction = self.JOGMOTION

        self.memberSelector = Member([22, 26, 23, 27], 0.2, self.selector)
        self.currentStep = 0.01
        self.currentVelocity = 100

        self.memberStartPause = Member([25], 0.2, self.startPause)
        self.lastStartPauseState = [0]

        self.active = Utils.getBool("CNC", "panel", 0)
        self.app = app
        self.lastCheck = time.time()

    def jog(self, pinValues):
        if self.app.running:
            return
        axis = pinValues[:-1]
        direction = pinValues[-1]
        if max(axis) == 0 and self.jogLastAction != self.JOGSTOP:
            self.app.focus_set()
            self.app.event_generate('<<JogStop>>', when="tail")
            self.jogLastAction = self.JOGSTOP
            return
        for id, ax in enumerate(axis):
            if ax == 1:
                con = self.axisMap[id] + self.directionMap[direction]
                self.app.focus_set()
                self.app.event_generate("<<"+con+">>", when="tail")
                self.jogLastAction = self.JOGMOTION

    def selector(self, selector: list):
        index = 0
        for id, w in enumerate(selector):
            if w == 1:
                index = id
        step = [0.01, 0.1, 1, 100][index]
        velocity = [5, 25, 50, 100][index]
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
            self.memberJog.check()
            self.memberStartPause.check()
            self.memberSelector.check()
            self.lastCheck = t