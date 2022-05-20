import threading
import time

try:
    import wiringpi as wp
except BaseException as be:
    print(be)

class Panel:
    def __init__(self, app, keys):
        try:
            wp.wiringPiSetup()
        except BaseException as be:
            print(be)

        self.jogLastTime = time.time()
        self.jogPeriod = 0.1
        self.axisPin = [21, 22]
        self.directionPin = [26]

        self.selectorLastTime = time.time()
        self.selectorPeriod = 0.2
        self.selectorPin = [23, 27]

        self.spLastTime = time.time()
        self.spPeriod = 0.2
        self.spPin = [25]

        try:
            for w in self.axisPin: wp.pinMode(w, wp.INPUT)
            for w in self.directionPin: wp.pinMode(w, wp.INPUT)
            for w in self.selectorPin: wp.pinMode(w, wp.INPUT)
            for w in self.spPin: wp.pinMode(w, wp.INPUT)
        except BaseException as be:
            print(be)

        self.app = app
        self.keys = keys
        self.lock = threading.Lock()

        self.axisMap = {1:"X", 2:"B", 3:"Z"}
        self.directionMap = {0:"+", 1:"-"}


        self.monitor = threading.Thread(target=self.monitorTask)
        self.monitor.start()


    def __del__(self):
        self.lock.acquire()
        self.monitor.join()

    def jog(self, axis, direction):
        con = self.axisMap[axis] + self.directionMap[direction]
        self.keys[con]()

    def selector(self, selector):
        step = [0.01, 0.1, 1, 1][selector]
        velocity = [5, 25, 50, 100][selector]
        self.app.control.setStep(step)
        self.app.gstate.overrideCombo('Feed')
        self.app.gstate.override.set(velocity)
        self.app.gstate.overrideChange()

    def startPause(self):
        self.app.pause()

    def monitorJog(self, t):
        try:
            axis = wp.digitalRead(self.axisPin[0])*2 + wp.digitalRead(self.axisPin[1])
            direction = wp.digitalRead(self.directionPin[0])
        except BaseException as be:
            print(be)
            axis = 0
            direction = 0
        if axis == 0:
            return
        if t > self.jogLastTime + self.jogPeriod:
            self.jogLastTime = t
            self.jog(axis, direction)

    def monitorSp(self, t):
        try:
            sp = wp.digitalRead(self.spPin[0])
        except BaseException as be:
            print(be)
            sp = 0
        if not sp:
            return
        if t > self.spLastTime + self.spPeriod:
            self.spLastTime = t
            self.startPause()

    def monitorSelector(self, t):
        try:
            selector = wp.digitalRead(self.selectorPin[0])*2 + wp.digitalRead(self.selectorPin[1])
        except BaseException as be:
            print(be)
            selector = 0
        if t > self.selectorLastTime + self.selectorPeriod:
            self.selectorLastTime = t
            self.selector(selector)

    def monitorTask(self):
        while 1:
            time.sleep(0.05)
            if self.lock.locked():
                return
            self.monitorJog()
            self.monitorSp()
            self.monitorSelector()


