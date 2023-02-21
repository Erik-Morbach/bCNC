def fun():
    if get("port1State") == 1:
        return
    set("port1State", 1)
    code("M62P1")
    set("Motor7Position", get("wa"))
    set("Motor8Position", get("wb"))
    set("Motor9Position", get("wc"))
    a, b, c = get("Motor10Position"), get("Motor11Position"), get("Motor12Position")
    b = -4
    code("G10 L20 P1 A{} B{} C{}".format(a,b,c))
    code("G4P0.05")
fun()
