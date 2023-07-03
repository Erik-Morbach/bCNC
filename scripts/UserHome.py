def code(st):
    self.sendGCode(st)
def setConnection(id, value):
    self.sendGCode("$%d=%d"%(id, value))
    self.sendGCode((8,100))

xConnection = 500
zConnection = 502
aConnection = 503

setConnection(zConnection,1)
code("$HZ")
code((4,))
setConnection(zConnection,2)
code("$HZ")
code((4,))
distance = CNC.vars["zGangedDifference"]
code("G91G0Z%.3f" % distance)
code((4,))
setConnection(zConnection, 3)
code("$HZ")
code((4,))

setConnection(xConnection, 1)
code("$HX")
code((4,))
setConnection(xConnection, 2)
code("$HX")
code((4,))
distance = CNC.vars["cavityDistance"] - CNC.vars["punctureDistance"]
code("G91G0X%.3f" % distance)
code((4,))
setConnection(xConnection, 3)
code("$HX")
code((4,))

code("$HY")
code((4,))

setConnection(aConnection, 1)
code("$HA")
code((4,))
code("G53 G0 A%.3f" % CNC.vars["a1Position"])
code((4,))
setConnection(aConnection, 2)
code("$HA")
code((4,))
code("G53 G0 A%.3f" % CNC.vars["a2Position"])
code("G53 G0 A%.3f" % CNC.vars["a2Position"])
code((4,))
code("$603=%.3f"%float(CNC.vars["a2Position"]))
code((4,))
