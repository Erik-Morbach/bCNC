import threading
import time
import wiringpi as wp

class Panel:
    def __init__(self, app, keys):
        wp.wiringPiSetup()

        self.jogLastTime = time.time()
        self.jogPeriod = 0.1
        self.axisPin = [2, 3, 4]
        self.directionPin = [21]

        self.selectorLastTime = time.time()
        self.selectorPeriod = 0.2
        self.selectorPin = [22, 26, 23, 27]
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

        self.axisMap = {1:"X", 2:"B", 4:"Z"}
        self.directionMap = {0:"Up", 1:"Down"}

        self.monitor = threading.Thread(target=self.monitorTask)
        self.monitor.start()

    def __del__(self):
        self.lock.acquire()
        self.monitor.join()

    def executeDelayed(self, timeout, function):
        def exec(timeoutt, functionn):
            time.sleep(timeoutt)
            functionn()
        threading.Thread(target=exec, args=(timeout, function)).start()

    def deboucePins(self, pins, timeout):
        time.sleep(timeout)
        value = [wp.digitalRead(w) for w in pins]
        return value

    def debounce(self, pin, timeout, function):
        def waitTime(pin_to_wait, time_to_wait, func):
            time.sleep(time_to_wait)
            if wp.digitalRead(pin_to_wait):
                func()
        threading.Thread(target=waitTime, args=(pin, timeout, function)).start()

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
        axis = 0
        power = 1
        pins = [wp.digitalRead(w) for w in self.axisPin]
        for w in pins:
            axis += w*power
            power *= 2
        direction = wp.digitalRead(self.directionPin[0])
        if axis == 0:
            return
        if t > self.jogLastTime + self.jogPeriod:
            self.jogLastTime = t
            def fun():
                pins2 = self.deboucePins(self.axisPin + self.directionPin, 0.01)
                direction2 = pins2[-1]
                del pins2[-1]
                if pins2 == pins and direction2 == direction:
                    self.jog(axis, direction)
            threading.Thread(target=fun).start()

    def monitorSp(self, t):
        sp = 0
        sp = wp.digitalRead(self.spPin[0])
        if not sp:
            return
        if t > self.spLastTime + self.spPeriod:
            self.spLastTime = t
            self.debounce(self.spPin[0], self.spPeriod, self.startPause)

    def monitorSelector(self, t):
        selector = 0
        power = 1
        for w in self.selectorPin:
            selector += wp.digitalRead(w)*power
            power *= 2
        if t > self.selectorLastTime + self.selectorPeriod:
            self.selectorLastTime = t
            def fun():
                selector2 = self.deboucePins(self.selectorPin, 0.01)
                power = 1
                s2 = 0
                for w in selector2:
                    s2 += w*power
                    power*=2
                if s2 == selector:
                    self.selector(selector)
            threading.Thread(target=fun).start()

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


