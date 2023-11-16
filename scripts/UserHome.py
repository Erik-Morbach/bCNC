def setConnection(id, value):
    code("$%d = %.3f"%(id, value))
    sleep()

xConnection = 500
zConnection = 502
bConnection = 504

setConnection(zConnection,1)
code("$HZ")
wait()
setConnection(zConnection,2)
code("$HZ")
wait()
# zGangedDifference is only a fine tune
distance = get("z_ganged_difference_base") + get("z_ganged_difference")
code("G91G0Z%.3f" % distance)
wait()
setConnection(zConnection, 3)
code("$HZ")
wait()

setConnection(xConnection, 1)
code("$HX")
wait()
setConnection(xConnection, 2)
code("$HX")
wait()
distance = get("cavity_distance") - get("puncture_distance")
code("G91G0X%.3f" % distance)
wait()
setConnection(xConnection, 3)
code("$HX")
wait()

newLimit = get("limit_x") - get("cavity_distance")
execute("MODIFY %d %.3f" % (130, newLimit))
sleep()

code("$HY")
wait()

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
