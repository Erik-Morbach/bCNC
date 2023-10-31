import HyIo
import panel.Member
import importlib
from configparser import ConfigParser
import panel.ContinuousUtils


class Panel:
    def __init__(self, app, filepath) -> None:
        self.app = app
        self.filepath = filepath
        self.config = ConfigParser()
        self.config.read(filepath)
        self.members = []
        self.continuousUtils = panel.ContinuousUtils.ContinuousUtils(0.016)  # 60fps

        self.initManager()

        self.initMembers()

        self.registerMembers()

    def initManager(self):
        if 'manager' not in self.config:
            raise RuntimeError("Manager not defined in panel.ini")
        if 'period' not in self.config['manager']:
            raise RuntimeError("Manager period not defined in panel.ini")
        period = float(self.config['manager']['period'])
        self.manager = HyIo.ioManager.IoManager(period)

    def initMembers(self):
        for member in self.config.sections():
            if member == 'manager':
                continue
            memberName = member
            memberConfig = self.config[member]
            pinIndex = 0
            pins = []
            while 1:
                pinName = "pin%d" % pinIndex
                if pinName not in memberConfig:
                    break
                pins.append(memberConfig[pinName])
                pinIndex += 1
            callbackName = memberConfig['callback']
            moduleFn = importlib.import_module(callbackName)

            continuous = False
            period = 0
            if 'continuous' in memberConfig:
                continuous = bool(memberConfig['continuous'])
                period = float(memberConfig['continuous_period'])

            memberObj = panel.Member.Member(self.app, self.manager, continuous,
                                            period, memberName, pins, moduleFn,
                                            self.continuousUtils)

            self.members.append(memberObj)

    def registerMembers(self):
        for member in self.members:
            member.register()

    def start(self):
        self.manager.startThread()
        self.continuousUtils.start()

    def stop(self):
        self.manager.stopThread()
        self.continuousUtils.stop()
