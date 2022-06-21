from enum import IntEnum
import threading
import numpy as np
import time
import tkinter

import Utils
from CNC import WAIT, CNC, GCode
import sys

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
        self.currentState = states.Waiting
        self.radiusZeroPosition = Utils.getFloat("Itece", "radiusZero", 0) # mm
        self.processLimitPosition = Utils.getFloat("Itece", "processLimitPosition", -100) # mm
        self.beginWaitTime = Utils.getFloat("Itece", "processBeginWait", 10) # segundos
        self.beginRpm = Utils.getFloat("Itece", "beginRpm", 4000) # rpm
        self.angularVelocity = Utils.getFloat("Itece", "defaultAngularVelocity", 125.66) # rad/s
        self.iterationDistance = Utils.getFloat("Itece", "iterationDistance", 0.2) # mm
        self.iterationFeed = Utils.getFloat("Itece", "iterationFeed", 20) # mm/min

    def start(self, *args) -> None:
        if self.mutex.locked():
            return
        self.thread = threading.Thread(target=self._process)
        self.mutex.acquire()
        self.thread.start()

    def end(self, *args) -> None:
        if not self.mutex.locked():
            return
        self.mutex.release()

    def _process(self) -> None:
        self._startupProcess()
        while self.mutex.locked():
            time.sleep(0.1)
            self._rpmCompensation()
            self._stateChange()
            if not self._isPositionValid():
                self.mutex.release()
                break
            if CNC.vars["state"] == "Idle":
                self._iteration()
        self._endProcess()

    def _startupProcess(self) -> None:
        self.app.sendGCode("%")
        self.app.configWidgets("state", tkinter.DISABLED)
        CNC.vars["jogActive"] = False
        self.app.sendGCode("G54")
        self.app.mcontrol._wcsSet("0",None,None,None,None,None)
        self.app.sendGCode("M3S{}".format(self.beginRpm))
        self.app.sendGCode("G4P{}".format(int(self.beginWaitTime))) # wait mainSpindle
        self.sleep(self.beginWaitTime)

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
        self.app.sendGCode("G90 G55 G0 X0")
        self.app.sendGCode("G54")
        self.app.configWidgets("state", tkinter.NORMAL)
        self._setState(states.Waiting)
        CNC.vars["jogActive"] = True
        self.app.sendGCode("%")

    def _isPositionValid(self) -> bool:
        return CNC.vars["mx"] > self.processLimitPosition

    def _activateMotors(self) -> None:
        self.app.sendGCode("M62P0") # activate Motor 0
        self.app.sendGCode("M62P1") # activate Motor 1

    def _deactivateMotors(self) -> None:
        self.app.sendGCode("M63P0") # activate Motor 0
        self.app.sendGCode("M63P1") # activate Motor 1
        self.app.sendGCode("M63P3") # activate Motor 1
        self.app.sendGCode("M67E0Q0")
        self.app.sendGCode("M67E1Q0")

    def _setLowSpeed(self) -> None:
        self.app.sendGCode("M62P3")
        self.app.sendGCode("M67E0Q{}".format(CNC.vars["motor0Low"]))
        self.app.sendGCode("M67E1Q{}".format(CNC.vars["motor1Low"]))

    def _setHighSpeed(self) -> None:
        self.app.sendGCode("M63P3")
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

    def _rpmCompensation(self) -> None:
        rpm = self._getDesiredRpm(self._getCurrentRadius(),
                                  self.angularVelocity)
        self.app.sendGCode("S{}".format(rpm))

    def _updateAngular(self,rpm) -> None:
        self.angularVelocity = self._getDesiredAngularVelocity(self._getCurrentRadius(), rpm)

    def _iteration(self) -> None:
        if self.currentState == states.Waiting:
            return
        self.app.sendGCode("G91G1X-0.2F20")
        while CNC.vars["state"] == "Run":
            time.sleep(0.01)

    def _setState(self, state):
        self.currentState = state
        CNC.vars["processState"] = state
        if state == states.Rotating:
            self._setLowSpeed()
        else:
            self._setHighSpeed()

    def _stateChange(self) -> None:
        s1 = (CNC.vars["inputs"] & 1) > 0
        s2 = (CNC.vars["inputs"] & 2) > 0

        if self.currentState == states.Waiting:
            if s1 == 1: self._setState(states.Entering)
            return
        if self.currentState == states.Entering:
            if (s1 == 1 and s2 == 1) or (s1==0 and s2==0): self._setState(states.Middle)
            elif s1 == 0 and s2 == 1: self._setState(states.Rotating)
            return
        if self.currentState == states.Middle:
            if s1 == 0 and s2 == 1: self._setState(states.Rotating)
            return
        if self.currentState == states.Rotating:
            if s1 == 1: self._setState(states.ReEntering)
            return
        if self.currentState == states.ReEntering:
            if (s1 == 0 and s2 == 0): self._setState(states.Exiting)
            return
        if self.currentState == states.Exiting:
            if s2 == 0: self._setState(states.Waiting)


