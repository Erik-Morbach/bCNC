def fun():
    if get("port0State") == 1:
        return
    set("port0State", 1)
    set("Motor1Position", get('wx'))
    set("Motor2Position", get('wy'))
    set("Motor3Position", get('wz'))
    x,y,z = get("Motor4Position"), get("Motor5Position"), get("Motor6Position")
    code("G10 L20 P1 X{} Y{} Z{}".format(x,y,z))
    code("M62 P0")
    code("G4 P0.1")
fun()
