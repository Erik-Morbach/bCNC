import threading
import sys
import functools
import time
import copy
from CNC import CNC
import Utils
import ThreadVar
import tkinter
from mttkinter import *

class JogController:
    def __init__(self, app, keys):
        print(sys.path)
        myConfigFile = open("jogConf.txt","r")
        self.mapKeyToCode = {}
        self.mapCodeToKey = {}
        for line in myConfigFile.readlines():
            key,code,sym = line.split(' ')
            sym = sym[:len(sym)-1]
            self.mapKeyToCode[key] = int(code),sym
            self.mapCodeToKey[int(code)] = key
        myConfigFile.close()

        self.app = app
        self.keys = keys

        self.jog = {}
        self.plannerLimit = Utils.getInt("Jog","planner", 90)
        self.period = Utils.getFloat("Jog", "debounce", 0.05)
        self.releasePeriod = Utils.getFloat("Jog", "beginPeriod", 0.05)
        self.lastTime = ThreadVar.ThreadVar(0.0)
        self.lastStop = ThreadVar.ThreadVar(0.0)
        self.mutex = threading.Lock()
        self.mutex.acquire()
        self.active = Utils.getBool("Jog", "keyboard", False)
        self.app.bind("<Key>", self.jogEvent)
        self.app.bind("<KeyRelease>", self.jogEvent)
        self.currentKeys = {}
        if self.active:
            for (key,(code,sym)) in self.mapKeyToCode.items():
                print("Bind {},{} to {}".format(code,sym,key))
                #self.app.bind("<"+str(sym)+">", self.jogEvent)
        self.mtx = threading.Lock()
        self.mtx.acquire()
        if self.active:
            self.updateTaskThread = threading.Thread(target=self.updateTask)
            self.updateTaskThread.start()

    def updateTask(self):
        while self.mtx.locked() and self.app is not None:
            time.sleep(self.period)
            self.update()
    def stopTask(self):
        self.mtx.release()

    def update(self):
        if self.app.running.val:
            return
        t = time.time()
        cp = copy.deepcopy(self.currentKeys)
        for (key, lastTime) in cp.items(): # Verify each key
            if lastTime>0:
                continue
            lastTime = -lastTime
            if t - lastTime >= self.period:
                if not self.mutex.locked() or CNC.vars["state"] == "Jog":
                    self.app.event_generate("<<JogStop>>", when="tail")
                    self.lastStop.value = time.time()
                    if CNC.vars["state"] != "Jog":
                        self.mutex.acquire()
                self.currentKeys.pop(key)

            
        #if t - self.lastTime.value >= self.period:
        #    if not self.mutex.locked() or CNC.vars["state"] == "Jog":
        #        self.currentKeys.clear()
        #        self.app.event_generate("<<JogStop>>", when="tail")
        #        self.lastStop.value = time.time()
        #        if CNC.vars["state"] != "Jog":
        #            self.mutex.acquire()

    def moveKeys(self, keys):
        mergedKeys = ""
        for curKey in keys:
            if curKey[0] in mergedKeys: continue
            mergedKeys += curKey
        self.app.control.move(mergedKeys[::2], mergedKeys[1::2])

    def jogEvent(self, eventData=None, simulatedData=None):
        if eventData is None and simulatedData is None: return
        if simulatedData is not None:
            keytype, keycode = simulatedData
        else:
            keytype = eventData.type
            keycode = eventData.keycode
        if keycode not in self.mapCodeToKey.keys():
            return
        if self.app.running.val or \
           CNC.vars["state"] == "Run" or \
           time.time() - self.lastStop.value < self.releasePeriod or \
           not CNC.vars["JogActive"]:
            return
        self.lastTime.value = time.time()
        if self.mutex.locked():
            self.mutex.release()
        if CNC.vars["planner"] < self.plannerLimit and CNC.vars["planner"]!=-1:
            return
        currentKey = self.mapCodeToKey[keycode]
        if keytype == tkinter.EventType.KeyPress:
            self.currentKeys[currentKey] = time.time()
        else:
            self.currentKeys[currentKey] = -time.time()
            return

        self.moveKeys(self.currentKeys.keys())
        #self.keys[currentKey](data)

