import wiringpi
import os

wiringpi.wiringPiSetupGpio()

pins = []

pins += [[20,21]]
pins += [[13,16,19,26]]
pins += [[5,12,6]]
pins += [[7,9,11,8]]
for block in pins:
    for pin in block:
        wiringpi.pinMode(pin, 0)

while 1:
    os.system("clear")
    st = ""
    for block in pins:
        st += "-"*20 + "\n"
        st += " ".join([str(w) for w in block]) + "\n"
        st += " ".join([str(wiringpi.digitalRead(w)) for w in block]) + "\n"
    print(st, end='')
