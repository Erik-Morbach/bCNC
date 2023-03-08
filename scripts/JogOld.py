if CNC.vars["jogOldStep"] != -1:
    self.control.step.set(CNC.vars["jogOldStep"])
    CNC.vars["jogOldStep"] = -1

