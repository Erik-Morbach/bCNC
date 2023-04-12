try:
    global clampToggleCounter
    clampToggleCounter
except:
    clampToggleCounter = 0
if self.serial is None or CNC.vars['state'].lower() not in ["idle"]: 
    pass
else:
    if clampToggleCounter % 2 == 0: self.serial_write(chr(0xA5))
    else: self.serial_write(chr(0xA6))
    self.serial.flush()
    clampToggleCounter+=1
