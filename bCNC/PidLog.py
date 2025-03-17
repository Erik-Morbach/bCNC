import time
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt

try:
    from Tkinter import *
    import Tkinter
except ImportError:
    from tkinter import *
    import tkinter as Tkinter

from mttkinter import *


class PidLogFrame(Frame, object):
    def __init__(self, master, app, *kw, **kwargs):
        Frame.__init__(self, master, *kw, **kwargs)
        self.app = app
        self.fig = Figure()

        Button(self, text="Reload", command=self.plotPid).pack(
            side=TOP, fill=X, expand=NO)

        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().pack(side=TOP, fill=BOTH, expand=YES)

    def plotPid(self, data=None):
        self.app.serial_write(chr(0xA2))
        self.app.serial.flush()
        time.sleep(2)
        plt.subplot(4, 1, 1)
        target = self.app.mcontrol.pidTarget[:]
        actual = self.app.mcontrol.pidActual[:]
        error = []
        for (u, v) in zip(target, actual):
            error += [u - v]
        plt.plot(self.app.mcontrol.pidTarget, color='blue')
        plt.subplot(4, 1, 2)
        plt.plot(self.app.mcontrol.pidActual, color='green')
        plt.subplot(4, 1, 3)
        plt.plot(self.app.mcontrol.pidError, color='yellow')
        plt.subplot(4, 1, 4)
        plt.plot(error, color='red')
        plt.show()
