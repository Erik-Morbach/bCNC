def m789():
    if get("port1State") == 0:
        return
    set("port1State", 0)
    code("M63P1")
    set("Motor10Position", get("wa"))
    set("Motor11Position", get("wb"))
    set("Motor12Position", get("wc"))
    a, b, c = get("Motor7Position"), get("Motor8Position"), get("Motor9Position")
    code("G10 L20 P1 A{} B{} C{}".format(a,b,c))
    code("G4P0.05")
m789()
set("currentJogAxis", 'B')
setVar("currentJogAxisNumber", 8)
