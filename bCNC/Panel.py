import threading
import time
import wiringpi as wp

class Panel:
    def __init__(self, app, keys):
        wp.wiringPiSetup()

        self.jogLastTime = time.time()
        self.jogPeriod = 0.1
        self.axisPin = [21, 22]
        self.directionPin = [26]

        self.selectorLastTime = time.time()
        self.selectorPeriod = 0.2
        self.selectorPin = [23, 27]
        self.currentStep = 0.01
        self.currentVelocity = 100

        self.spLastTime = time.time()
        self.spPeriod = 0.2
        self.spPin = [25]

        for w in self.axisPin + self.directionPin + self.selectorPin + self.spPin:
            wp.pinMode(w, wp.INPUT)
            wp.pullUpDnControl(w, wp.PUD_DOWN)

        self.app = app
        self.keys = keys
        self.lock = threading.Lock()

        self.axisMap = {1:"X", 2:"B", 3:"Z"}
        self.directionMap = {0:"Up", 1:"Down"}

        self.monitor = threading.Thread(target=self.monitorTask)
        self.monitor.start()

    def __del__(self):
        self.lock.acquire()
        self.monitor.join()

    def jog(self, axis, direction):
        con = self.axisMap[axis] + self.directionMap[direction]
        print("Joging to", con)
        self.app.event_generate("<<"+con+">>", when="tail")

    def selector(self, selector):
        step = [0.01, 0.1, 1, 1][selector]
        velocity = [5, 25, 50, 100][selector]
        self.currentStep = step
        self.currentVelocity = velocity
        self.app.event_generate("<<AdjustSelector>>", when="tail")

    def startPause(self):
        self.app.pause()

    def monitorJog(self, t):
        axis = wp.digitalRead(self.axisPin[0])*2 + wp.digitalRead(self.axisPin[1])
        direction = wp.digitalRead(self.directionPin[0])
        if axis == 0:
            return
        if t > self.jogLastTime + self.jogPeriod:
            self.jogLastTime = t
            self.jog(axis, direction)

    def monitorSp(self, t):
        sp = 0
        sp = wp.digitalRead(self.spPin[0])
        if not sp:
            return
        if t > self.spLastTime + self.spPeriod:
            self.spLastTime = t
            self.startPause()

    def monitorSelector(self, t):
        selector = wp.digitalRead(self.selectorPin[0])*2 + wp.digitalRead(self.selectorPin[1])
        if t > self.selectorLastTime + self.selectorPeriod:
            self.selectorLastTime = t
            self.selector(selector)

    def monitorTask(self):
        while 1:
            time.sleep(0.5)
            if self.lock.locked():
                return
            t = time.time()
            try:
                self.monitorJog(t)
                self.monitorSp(t)
                self.monitorSelector(t)
            except BaseException as be:
                print(be)
                time.sleep(3)
                pass


