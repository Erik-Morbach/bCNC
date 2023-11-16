def setConnection(id, value):
    code("$%d = %.3f"%(id, value))
    sleep()

xConnection = 500
zConnection = 502
bConnection = 504

setConnection(bConnection, 3)
code("$HB")
wait()
setConnection(bConnection, 1)
code("$HB")
wait()
code("G53 G0 B%.3f" % get("b1_position"))
wait()
setConnection(bConnection, 2)
code("$HB")
wait()
code("G53 G0 B%.3f" % get("b2_position"))
wait()
setConnection(bConnection, 3)
code("$604=0")
wait()
