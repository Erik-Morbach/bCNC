import threading
import sys
import functools
import time
from CNC import CNC
import Utils

class JogController:
    def __init__(self, app, keys):
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
        self.lastTime = 0
        self.lastStop = 0
        self.mutex = threading.Lock()
        self.mutex.acquire()
        self.active = Utils.getBool("Jog", "keyboard", False)
        if self.active:
            for (key,(code,sym)) in self.mapKeyToCode.items():
                print("Bind {},{} to {}".format(code,sym,key))
                self.app.bind("<"+str(sym)+">", self.jogEvent)
        self.mtx = threading.Lock()
        self.mtx.acquire()
        self.updateTaskThread = threading.Thread(target=self.updateTask)
        self.updateTaskThread.start()

    def updateTask(self):
        while self.mtx.locked():
            time.sleep(self.period)
            self.update()
    def stopTask(self):
        self.mtx.release()

    def update(self):
        if self.app.running:
            return
        t = time.time()
        if t - self.lastTime >= self.period:
            if not self.mutex.locked() or CNC.vars["state"] == "Jog":
                self.app.event_generate("<<JogStop>>", when="tail")
                self.lastStop = time.time()
                if CNC.vars["state"] != "Jog":
                    self.mutex.acquire()

    def jogEvent(self, data):
        if self.app.running or \
           CNC.vars["state"] == "Run" or \
           data is None or \
           time.time() - self.lastStop < self.releasePeriod or \
           not CNC.vars["JogActive"]:
            return
        self.lastTime = time.time()
        if self.mutex.locked():
            self.mutex.release()
        if CNC.vars["planner"] < self.plannerLimit and CNC.vars["planner"]!=-1:
            return
        self.keys[self.mapCodeToKey[data.keycode]](data)

