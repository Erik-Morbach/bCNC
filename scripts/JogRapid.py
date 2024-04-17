if CNC.vars["jogOldStep"] == -1:
    CNC.vars["jogOldStep"] = self.control.step.get()
self.control.step.set(100)
