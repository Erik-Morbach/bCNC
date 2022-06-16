from enum import IntEnum
import threading
import numpy as np
import time

import Utils
from CNC import CNC

class states(IntEnum):
    Waiting = 0,
    Entering = 1,
    Middle = 2,
    Rotating = 3,
    ReEntering = 4,
    Exiting = 5


class IteceProcess:
    def __init__(self, app) -> None:
        self.mutex = threading.Lock()
        self.app = app
        self.currentState = 0
        self.radiusZeroPosition = Utils.getFloat("Itece", "radiusZero", 0)
        self.beginRpm = Utils.getFloat("Itece", "beginRpm", 4000) # rpm
        self.angularVelocity = Utils.getFloat("Itece", "defaultAngularVelocity", 125.66) # rad/s

    def start(self) -> None:
        if self.mutex.locked():
            return
        self.app.processInit()
        self.thread = threading.Thread(target=self._process)
        self.mutex.acquire()
        self.thread.start()

    def _activateMotors(self) -> None:
        self.app.sendGCode("M62P0") # activate Motor 0
        self.app.sendGCode("M62P1") # activate Motor 1

    def _deactivateMotors(self) -> None:
        self.app.sendGCode("M63P0") # activate Motor 0
        self.app.sendGCode("M63P1") # activate Motor 1
        self.app.sendGCode("M67E0Q0")
        self.app.sendGCode("M67E1Q0")

    def _setLowSpeed(self) -> None:
        self.app.sendGCode("M67E0Q{}".format(CNC.vars["motor0Low"]))
        self.app.sendGCode("M67E1Q{}".format(CNC.vars["motor1Low"]))

    def _setHighSpeed(self) -> None:
        self.app.sendGCode("M67E0Q{}".format(CNC.vars["motor0High"]))
        self.app.sendGCode("M67E1Q{}".format(CNC.vars["motor1High"]))

    def _getDesiredRpm(self, radius, angularVelocity) -> float:
        return angularVelocity / (2 * np.pi * radius)

    def _getDesiredAngularVelocity(self, radius, rpm) -> float:
        return rpm * 2 * np.pi * radius

    def _getCurrentRadius(self) -> float:
        return CNC.vars["mx"] - self.radiusZeroPosition

    def sleep(self, t) -> None:
        while t > 0:
            time.sleep(0.1)
            t -= 0.1
            CNC.vars["wait"] = t
        CNC.vars["wait"] = 0

    def _startupProcess(self) -> None:
        self.app.mcontrol._wcsSet("0",None,None,None,None,None)
        self.app.sendGCode("M3S{}".format(self.beginRpm))
        self.app.sendGCode("G4P10") # wait mainSpindle
        self.sleep(10)

        self.angularVelocity = self._getDesiredAngularVelocity(self._getCurrentRadius(), 
                                                               self.beginRpm)

        self._setHighSpeed()
        self._activateMotors()
        self.app.sendGCode("M62P2") # presser
        self.app.sendGCode("G4P1") #  wait Presser
        self.sleep(1)

    def _endProcess(self) -> None:
        self.app.sendGCode("M5")
        self._deactivateMotors()

    def _rpmCompensation(self) -> None:
        rpm = self._getDesiredRpm(self._getCurrentRadius(),
                                  self.angularVelocity)
        self.app.sendGCode("M3S{}".format(rpm))

    def _update(self) -> None:
        self.angularVelocity = self._getDesiredAngularVelocity(self._getCurrentRadius(),
                                                               CNC.vars["curspindle"])

    def _iteration(self) -> None:
        pass

    def _stateChange(self) -> None:
        pass

    def _process(self) -> None:
        self._startupProcess()
        while self.mutex.locked():
            self._rpmCompensation()
            self._stateChange()
            if CNC.vars["state"] == "Idle":
                self._iteration()
        self._endProcess()

    def end(self) -> None:
        if not self.mutex.locked():
            return
        self.mutex.release()
        self.app.processEnd()

