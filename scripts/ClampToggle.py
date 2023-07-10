clampToggleName = "ClampToggleCounter"
if not exist(clampToggleName):
    set(clampToggleName, 0)
print("Clamp State = ", get(clampToggleName))
if self.serial is None or get('state').lower() not in ["idle"]: 
    pass
else:
    if get(clampToggleName) % 2 == 0: self.serial_write(chr(0xA5))
    else: self.serial_write(chr(0xA6))
    self.serial.flush()
    set(clampToggleName, get(clampToggleName) + 1)
    
