def fun():
    if get("port0State") == 0:
        return
    set("port0State", 0)
    set("Motor4Position", get('wx'))
    set("Motor5Position", get('wy'))
    set("Motor6Position", get('wz'))
    x,y,z = get("Motor1Position"), get("Motor2Position"), get("Motor3Position")
    code("G10 L20 P1 X{} Y{} Z{}".format(x,y,z))
    code("M63P0")
    code("G4P0.1")
fun()
