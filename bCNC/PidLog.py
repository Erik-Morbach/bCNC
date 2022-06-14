import matplotlib
matplotlib.use('TkAgg')
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

import time

try:
	from Tkinter import *
	import Tkinter
except ImportError:
	from tkinter import *
	import tkinter as Tkinter


class PidLogFrame(Frame, object):
	def __init__(self, master, app, *kw, **kwargs):
		Frame.__init__(self, master, *kw, **kwargs)
		self.app = app
		self.fig = Figure()

		Button(self,text="Reload", command=self.plotPid).pack(side=TOP, fill=X, expand=NO)

		self.canvas = FigureCanvasTkAgg(self.fig, master=self)
		self.canvas.get_tk_widget().pack(side=TOP, fill=BOTH, expand=YES)

	def plotPid(self, data=None):
		self.app.serial_write(chr(0xA2))
		self.app.serial.flush()
		time.sleep(1)
		self.fig.clear(True)
		ax = self.fig.add_subplot(111)
		target = self.app.mcontrol.pidTarget[:]
		actual = self.app.mcontrol.pidActual[:]
		error = []
		for (u,v) in zip(target, actual):
			error += [u - v]

		if len(error) > 0:
			maxError = max(abs(max(error)), abs(min(error)))
			ax.ylim(-abs(maxError),abs(maxError))
		ax.plot(self.app.mcontrol.pidTarget, color='blue')
		ax.plot(self.app.mcontrol.pidActual, color='green')
		ax.plot(error, color='red')
		self.canvas.draw()

