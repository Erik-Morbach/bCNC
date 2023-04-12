clampToggleName = "ClampToggleCounter"
if clampToggleName not in CNC.vars.keys():
    CNC.vars[clampToggleName] = 0
print(CNC.vars[clampToggleName])
if self.serial is None or CNC.vars['state'].lower() not in ["idle"]: 
    pass
else:
    if CNC.vars[clampToggleName] % 2 == 0: self.serial_write(chr(0xA5))
    else: self.serial_write(chr(0xA6))
    self.serial.flush()
    CNC.vars[clampToggleName] += 1
    
