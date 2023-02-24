def m123():
    if get("port0State") == 0:
        return
    set("port0State", 0)
    code("M63P0")
    set("Motor4Position", get("wx"))
    set("Motor5Position", get("wy"))
    set("Motor6Position", get("wz"))
    x, y, z = get("Motor1Position"), get("Motor2Position"), get("Motor3Position")
    code("G10 L20 P1 X{} Y{} Z{}".format(x,y,z))
    send((8,2))
    code("G4P0.05")
m123()
set("currentJogAxis", 'Z')
setVar("currentJogAxisNumber", 3)
