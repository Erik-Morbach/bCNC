def setConnection(id, value):
    execute("MODIFY %d %.3f"%(id, value))
    sleep()

xConnection = 500
zConnection = 502
aConnection = 503

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

newLimit = get("limit_x") - distance
execute("MODIFY %d %.3f" % (130, newLimit))
sleep()

code("$HY")
wait()

setConnection(aConnection, 3)
code("$HA")
wait()
setConnection(aConnection, 1)
code("$HA")
wait()
code("G53 G0 A%.3f" % get("a1_position"))
wait()
setConnection(aConnection, 2)
code("$HA")
wait()
code("G53 G0 A%.3f" % get("a2_position"))
wait()
code("$603=%.3f"%float(get("a2_position")))
wait()
