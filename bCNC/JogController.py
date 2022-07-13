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
        self.period = 0.05
        self.releasePeriod = 0
        self.lastTime = 0
        self.lastStop = 0
        self.mutex = threading.Lock()
        self.active = Utils.getBool("Jog", "keyboard", False)
        if self.active:
            for (key,(code,sym)) in self.mapKeyToCode.items():
                print("Bind {},{} to {}".format(code,sym,key))
                self.app.bind("<"+str(sym)+">", self.jogEvent)
    def update(self):
        if not self.active or self.app.running:
            return
        t = time.time()
        if t - self.lastTime >= self.period and not self.mutex.locked():# and t - self.lastStop >= self.period:
            self.app.event_generate("<<JogStop>>", when="tail")
            self.lastStop = time.time()
            if CNC.vars["state"] == "Idle":
                self.mutex.acquire()

    def jogEvent(self, data):
        if self.app.running or CNC.vars["state"] == "Run" or data is None or time.time() - self.lastStop < self.releasePeriod:
            return
        self.lastTime = time.time()
        if self.mutex.locked():
            self.mutex.release()
        if CNC.vars["planner"] < 10:
            return
        self.keys[self.mapCodeToKey[data.keycode]](data)

