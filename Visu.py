import matplotlib.pyplot as plt
import sys
import struct

file = open(sys.argv[1],'rb')
raw = file.read()
file.close()
print(len(raw))
quantity = len(raw)//8
print(struct.calcsize(quantity*'q'))
values = list(struct.unpack(quantity * 'q',raw))
print(values)
x = []
y = []
z = []

for i in range(0,len(values), 6):
    x += [(values[i],values[i+1])]
    y += [(values[i+2],values[i+3])]
    z += [(values[i+4],values[i+5])]


vectors = [x,y,z]
indexes = [1,2,3]

for (index,vector) in zip(indexes, vectors):
    plt.subplot(3,1, index)
    work = [w[1] for w in vector]
    machine = [w[1] for w in vector]
    if len(machine)>1:
        machine = machine[1:]
        work = work[1:]
    for i in range(len(machine)):
        machine[i] -= machine[0]
        if i > 1:
            work[i] = machine[i] - machine[i-1]
    plt.plot(work, c='blue')
    plt.plot(machine, c='red')
plt.show()
