from HyIo.parser import Parser
import ThreadVar
import functools

parser = Parser()
uniqueId = ThreadVar.ThreadVar(0)


class Member:
    def __init__(self, app, manager, continuous, period, memberName, pins,
                 moduleFn, continuousUtils):
        self.app = app
        self.manager = manager
        self.continuous = continuous
        self.period = period
        self.memberName = memberName
        self.continuousUtils = continuousUtils
        self.loadPins(pins)
        self.moduleFn = moduleFn
        self.myId = uniqueId.assign(lambda x: x+1)
        self.lastValue = None

    def loadPins(self, pins):
        global parser
        self.pins = []
        for pin in pins:
            self.pins.append(parser.getPin(pin))

    def register(self):
        for pin in self.pins:
            pin.setup()
            self.manager.registerPin(pin, self.callback)

    def validate(self, value):
        if isinstance(value, list):
            return True
        return bool(value)

    def callback(self, value):
        if self.continuous:
            if value == self.lastValue:
                return
            self.lastValue = value
            self.continuousUtils.removeMember(self.myId)
            fn = functools.partial(self.moduleFn.run, value)
            self.continuousUtils.registerMember(self.myId, fn, self.period)

        else:
            self.moduleFn.run(value)
