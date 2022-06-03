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
        for line in myConfigFile.readlines():
            key,code,sym = line.split(' ')
            sym = sym[:len(sym)-1]
            self.mapKeyToCode[key] = int(code),sym
        myConfigFile.close()

        self.app = app  
        self.keys = keys

        self.jog = {}
		
        self.lastTime = 0
        self.mutex = threading.Lock()
        if Utils.getBool("Panel", "jogKeyboard", False):
            for (key,(code,sym)) in self.mapKeyToCode.items():
                print("Bind {},{} to {}".format(code,sym,key))
                self.app.bind("<"+str(sym)+">", functools.partial(self.jogEvent,key))
            threading.Thread(target=self.waitToStop).start()
    def waitToStop(self):
        while 1:
            self.mutex.acquire(blocking=True)
            if self.app.running:
                continue
            time.sleep(0.1)
            if time.time() - self.lastTime >= 0.1:
                try:
                    self.app.event_generate("<<JogStop>>", when="tail")
                except:
                    pass

    def jogEvent(self,key, data):
        if self.app.running:
            return
        self.lastTime = time.time()
        if self.mutex.locked():
            self.mutex.release()
        self.keys[key]()

