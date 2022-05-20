import threading
import time
import wiringpi as wp
import Utils

def debounce(pin, timeout, function):
    def waitTime():
        val = wp.digitalRead(pin)
        time.sleep(timeout)
        if val == wp.digitalRead(pin) and val:
            function()
    threading.Thread(target=waitTime).start()


def deboucePins(pins, timeout):
    old_value = [wp.digitalRead(w) for w in pins]
    time.sleep(timeout)
    current_value = [wp.digitalRead(w) for w in pins]
    return [i and j for (i, j) in zip(old_value, current_value)]


def executeDelayed(timeout, function):
    def foo():
        time.sleep(timeout)
        function()
    threading.Thread(target=foo).start()


class Panel:
    def __init__(self, app, keys):
        wp.wiringPiSetup()

        self.jogLastState = 2
        self.jogLastTime = time.time()
        self.jogPeriod = 0.1
        self.jogDebounce = 0.01
        self.axisPin = [2, 3, 4]
        self.directionPin = [21]

        self.selectorLastTime = time.time()
        self.selectorPeriod = 0.2
        self.selectorDebounce = 0.1
        self.selectorPin = [22, 26, 23, 27]
        self.currentStep = 0.01
        self.currentVelocity = 100

        self.spLastTime = time.time()
        self.spPeriod = 0.2
        self.spDebounce = 0.5
        self.spPin = [25]

        for w in self.axisPin + self.directionPin + self.selectorPin + self.spPin:
            wp.pinMode(w, wp.INPUT)
            wp.pullUpDnControl(w, wp.PUD_DOWN)

        self.app = app
        self.keys = keys
        self.lock = threading.Lock()

        self.axisMap = {1:"X", 2:"B", 4:"Z"}
        self.directionMap = {0:"Up", 1:"Down"}

        self.monitor = threading.Thread(target=self.monitorTask)
        if Utils.getBool("CNC", "Panel", False):
            self.monitor.start()

    def close(self):
        self.lock.acquire()
        if self.monitor.isAlive():
            self.monitor.join()

    def jog(self, axis, direction):
        if axis == 0:
            if self.jogLastState == 2:
                self.app.event_generate('<<JogStop>>', when="tail")
            self.jogLastState = 1
            return
        for w in range(0, 3):
            ax = 2 ** w
            if axis & ax == ax:
                con = self.axisMap[ax] + self.directionMap[direction]
                self.app.event_generate("<<"+con+">>", when="tail")
                self.jogLastState = 2

    def selector(self, selector):
        step = [0.01, 0.1, 1, 1][min(selector,3)]
        velocity = [5, 25, 50, 100][min(selector,3)]
        if step != self.currentStep or velocity != self.currentVelocity:
            self.currentStep = step
            self.currentVelocity = velocity
            self.app.event_generate("<<AdjustSelector>>", when="tail")

    def startPause(self):
        self.app.pause()

    def monitorJog(self, t):
        if t > self.jogLastTime + self.jogPeriod:
            def fun():
                pin_values = deboucePins(self.axisPin + self.directionPin, self.jogDebounce)
                axis = sum([w * 2 ** index for (index, w) in enumerate(pin_values[:-1])])
                direction = pin_values[-1]
                self.jogLastTime = time.time()
                self.jog(axis, direction)
            threading.Thread(target=fun).start()

    def monitorSp(self, t):
        if t > self.spLastTime + self.spPeriod:
            def fun():
                self.spLastTime = time.time()
                self.startPause()
            debounce(self.spPin[0], self.spDebounce, fun)

    def monitorSelector(self, t):
        if t > self.selectorLastTime + self.selectorPeriod:
            def fun():
                selector = deboucePins(self.selectorPin, self.selectorDebounce)
                selector = sum([w * index for (index, w) in enumerate(selector)])
                self.selectorLastTime = time.time()
                self.selector(selector)
            threading.Thread(target=fun).start()

    def monitorTask(self):
        while 1:
            time.sleep(0.05)
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


