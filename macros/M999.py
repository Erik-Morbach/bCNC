code("M123")
code("M456")
for i in range(7, 13):
    code("#Motor{}Position".format(i), -4)
code("M789")
code("M101112")
for i in range(1, 7):
    code("#Motor{}Position".format(i), -4)
