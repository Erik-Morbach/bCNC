import os
import gpiozero


pins = []

pins += [[20,21]]
pins += [[13,16,19,26]]
pins += [[5,12,6]]
pins += [[7,9,11,8]]
obj = []
for block in pins:
    obj += [[]]

    for pin in block:
        obj[-1] += [gpiozero.Button(pin, pull_up=False)]

while 1:
    os.system("clear")
    st = ""
    for (pins, ob) in zip(pins, obj):
        st += "-"*20 + "\n"
        st += " ".join([str(w) for w in pins]) + "\n"
        st += " ".join([str(w.is_pressed) for w in ob]) + "\n"
    print(st, end='')
