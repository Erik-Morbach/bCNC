from enum import IntEnum
import functools
from os import wait
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

class State:
    _variablesToId: dict = {}
    _idToUpdateMethod: dict = {}
    _idToUpdateFlag: dict = {}
    _idToValue: dict = {}
    _idCounter = 0
    def __init__(self):
        self._variablesToId = {}
        self._idToUpdateMethod = {}
        self._idToUpdateFlag = {}
        self._idToValue = {}
        self._idCounter = 0

    def showState(self):
        print(self._variablesToId)
        print(self._idToValue)
        print(self._idToUpdateFlag)

    def _getVariableId(self, name):
        if self._variablesToId.get(name) is None:
            self._variablesToId[name] = self._getNewId()
        return self._variablesToId[name]

    def _getNewId(self):
        self._idCounter += 1
        return self._idCounter

    def createVariable(self, name, value, updateMethod):
        self.setValue(name, value)
        self.setUpdateMethod(name, updateMethod)

    def setValue(self, name, value):
        currentId = self._getVariableId(name)
        self._idToValue[currentId] = value
        self._idToUpdateFlag[currentId] = True

    def setUpdateMethod(self, name, updateMethod):
        currentId = self._getVariableId(name)
        self._idToUpdateMethod[currentId] = updateMethod

    def getValue(self, name):
        currentId = self._getVariableId(name)
        return self._idToValue[currentId]

    def clearUpdateFlag(self, name):
        currentId = self._getVariableId(name)
        self._idToUpdateFlag[currentId] = False

    def update(self, name = ""):
        currentId = self._getVariableId(name)
        try:
            value = self._idToValue[currentId]
            self._idToUpdateMethod[currentId](value)
        except BaseException as be:
            print("While executing update method of {}:{}".format(name))
            print(be)
            print("passing....")

    def executeUpdateMethods(self, variables=None):
        if variables is None:
            variables = [w for w in self._variablesToId.keys()]
        for name in variables:
            if self.shouldUpdate(name):
                self.update(name)
                self.clearUpdateFlag(name)

    def shouldUpdate(self, name):
        currentId = self._getVariableId(name)
        return self._idToUpdateFlag[currentId]

class IteceProcess:
    def __init__(self, app) -> None:
        self.mutex = threading.Lock()
        self.app = app
        self.currentState = states.Waiting
        self.spindleDeadBand = Utils.getFloat("Itece", "spindleDeadBand", 50)
        self.pwmResolution = Utils.getFloat("Itece", "pwmResolution", 1024)
        self.radiusZeroPosition = Utils.getFloat("Itece", "radiusZero", 0) # mm
        self.processLimitPosition = Utils.getFloat("Itece", "processLimitPosition", -100) # mm
        self.beginWaitTime = Utils.getFloat("Itece", "processBeginWait", 10) # segundos
        self.beginRpm = Utils.getFloat("Itece", "beginRpm", 4000) # rpm
        self.angularVelocity = Utils.getFloat("Itece", "defaultAngularVelocity", 125.66) # rad/s
        self.iterationDistance = Utils.getFloat("Itece", "iterationDistance", 0.2) # mm
        self.iterationFeed = Utils.getFloat("Itece", "iterationFeed", 20) # mm/min

        self.updateVelocityMethod = self._updateToHighSpeed

        self.state = State()
        def sendRpm(rpm):
            self.app.sendGCode("S{}".format(rpm))
        self.state.createVariable("rpm", self.beginRpm, sendRpm)

        def sendVelocity(ind,vel):
            self.app.sendGCode("M67E{}Q{}".format(ind, vel))
        self.state.createVariable("motor0",
                                  CNC.vars["motor0High"]/100 * self.pwmResolution,
                                  functools.partial(sendVelocity, 0))
        self.state.createVariable("motor1",
                                  CNC.vars["motor1High"]/100 * self.pwmResolution,
                                  functools.partial(sendVelocity, 1))

    def isRunning(self) -> bool:
        return self.mutex.locked()

    def isPositionValid(self, position) -> bool:
        return 0 <= position and position < self.processLimitPosition

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

    def setNewRpm(self, rpm) -> None:
        self._updateAngular(rpm)

    def _process(self) -> None:
        self._startupProcess()
        while self.mutex.locked():
            time.sleep(0.1)
            self._rpmCompensation()
            self._stateChange()
            self.updateVelocityMethod()
            self.state.executeUpdateMethods()

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
        self.app.sendGCode("G10L2P1X0")
        #self.app.mcontrol._wcsSet("0",None,None,None,None,None)
        self.app.sendGCode("M3S{}".format(self.beginRpm))
        self._setHighSpeed()
        self._activateMotors()
        self.state.executeUpdateMethods()
        self.app.sendGCode("G4P{}".format(int(self.beginWaitTime))) # wait mainSpindle
        self.sleep(self.beginWaitTime)

        self.angularVelocity = self._getDesiredAngularVelocity(self._getCurrentRadius(), 
                                                               self.beginRpm)
        self.app.sendGCode("M62P2") # presser
        self.app.sendGCode("G4P1") #  wait Presser
        self.app.sendGCode("M8")
        self.sleep(1)

    def _endProcess(self) -> None:
        self.app.sendGCode("M5")
        self.app.sendGCode("M63P2") # presser
        self._setState(states.Waiting)
        self._deactivateMotors()
        self.app.sendGCode("G90 G55 G0 X0")
        self.app.sendGCode("G54")
        self.app.configWidgets("state", tkinter.NORMAL)
        CNC.vars["jogActive"] = True
        self.app.sendGCode("M9")
        self.app.sendGCode("%")

    def _isPositionValid(self) -> bool:
        return abs(CNC.vars["mx"]) < abs(self.processLimitPosition)

    def _activateMotors(self) -> None:
        self.app.sendGCode("M62P0") # activate Motor 0
        self.app.sendGCode("M62P1") # activate Motor 1

    def _deactivateMotors(self) -> None:
        self.app.sendGCode("M63P0") # activate Motor 0
        self.app.sendGCode("M63P1") # activate Motor 1
        self.state.setValue("motor0", 0)
        self.state.setValue("motor1", 0)

    def _updateToLowSpeed(self):
        m0Low = float(CNC.vars["motor0Low"])/100 * self.pwmResolution
        m1Low = float(CNC.vars["motor1Low"])/100 * self.pwmResolution
        if m0Low != self.state.getValue("motor0"):
            self.state.setValue("motor0", m0Low)
        if m1Low != self.state.getValue("motor1"):
            self.state.setValue("motor1", m1Low)

    def _updateToHighSpeed(self):
        m0High = float(CNC.vars["motor0High"])/100 * self.pwmResolution
        m1High = float(CNC.vars["motor1High"])/100 * self.pwmResolution
        if m0High != self.state.getValue("motor0"):
            self.state.setValue("motor0", m0High)
        if m1High != self.state.getValue("motor1"):
            self.state.setValue("motor1", m1High)

    def _setLowSpeed(self) -> None:
        self._updateToLowSpeed()
        self.updateVelocityMethod = self._updateToLowSpeed

    def _setHighSpeed(self) -> None:
        self._updateToHighSpeed()
        self.updateVelocityMethod = self._updateToHighSpeed

    def _getDesiredRpm(self, radius, angularVelocity) -> float:
        return angularVelocity / (2 * np.pi * radius)

    def _getDesiredAngularVelocity(self, radius, rpm) -> float:
        return rpm * 2 * np.pi * radius

    def _getCurrentRadius(self) -> float:
        return abs(CNC.vars["mx"] - self.radiusZeroPosition)

    def sleep(self, t) -> None:
        while t > 0:
            if not self.mutex.locked():
                CNC.vars["wait"] = 0
                return
            time.sleep(0.1)
            t -= 0.1
            CNC.vars["wait"] = t
        CNC.vars["wait"] = 0

    def _rpmCompensation(self) -> None:
        newRpm = self._getDesiredRpm(self._getCurrentRadius(), self.angularVelocity)
        if abs(newRpm - self.state.getValue("rpm")) > self.spindleDeadBand:
            self.state.setValue("rpm", newRpm)

    def _updateAngular(self,rpm) -> None:
        self.angularVelocity = self._getDesiredAngularVelocity(self._getCurrentRadius(), rpm)

    def _iteration(self) -> None:
        if self.currentState == states.Waiting:
            return
        self.app.sendGCode("G91G1X{}F{}".format(self.iterationDistance, self.iterationFeed))

    def _setState(self, state):
        self.currentState = state
        CNC.vars["processState"] = state
        if state == states.Rotating:
            self.updateVelocityMethod = self._setLowSpeed
        else:
            self.updateVelocityMethod = self._setHighSpeed

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
            if s2 == 1: self._setState(states.Exiting)
            return
        if self.currentState == states.Exiting:
            if s2 == 0: self._setState(states.Waiting)


