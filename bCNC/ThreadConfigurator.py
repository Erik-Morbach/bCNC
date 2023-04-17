from tkinter import *
import tkinter
import threading
import copy
import time
from tkinter.simpledialog import Dialog
from tkinter.messagebox import askokcancel
from ControlPage import DROFrame
import Utils
from mttkinter import *

from CNC import WAIT, WCS, CNC

class ThreadInfo:
	def __init__(self):
		self.rpm = DoubleVar(value=1000)
		self.tool = IntVar(value=0)
		self.m3Wait = DoubleVar(value=2)
		self.pitch = DoubleVar(value=1)
		self.depth = DoubleVar(value=1)
		self.depthIncrementPerPass = DoubleVar(value=0.2)
		self.depthDegression = DoubleVar(value=1)
		self.startZ = DoubleVar()
		self.endZ = DoubleVar()
		self.startX = DoubleVar()
		self.beginThreadCutOnX = DoubleVar()
		self.taperDistance = DoubleVar(value=1)
		self.entryTaper = BooleanVar(value=False)
		self.exitTaper = BooleanVar(value=True)
		self.slideAngle = DoubleVar(value=30)
		self.springPasses = IntVar(value=2)
	def generateGCode(self):
		gcode = "M6 T{} G43 H{}\n".format(self.tool.get(), self.tool.get())
		gcode += "M3 S%.1f\n" % self.rpm.get()
		gcode += "G4 P%.1f\n" % self.m3Wait.get()
		gcode += "G0 Z%.4f X%.4f\n" % (self.startZ.get(), self.startX.get())
		z = self.endZ.get()
		i = self.beginThreadCutOnX.get() - self.startX.get()
		p = self.pitch.get()
		k = self.depth.get()
		j = self.depthIncrementPerPass.get()
		r = self.depthDegression.get()
		q = self.slideAngle.get()
		h = self.springPasses.get()
		l = 0
		if self.entryTaper.get():
			l += 1
		if self.exitTaper.get():
			l += 2
		e = self.taperDistance.get()
		gcode += "G76 Z%.4f I%.4f P%.4f K%.4f J%.4f R%.2f Q%.2f H%d E%d L%.4f\n" % (z, i, p, k, j, r, q, h, e, l)
		gcode += "G0 Z%.4f X%.4f\n" % (self.startZ.get(), self.startX.get())
		gcode += "M48\n"
		gcode += "M53\n"
		return gcode


class ThreadConfigurator(Dialog):
	def __init__(self, parent, title, app):
		self.app = app
		self.parent = parent
		self.info = ThreadInfo()
		self.text = None
		self.myThread = None
		self.stopThread = False
		Dialog.__init__(self, parent, title)

	def body(self, frame):
		vcmd = (frame.register(self.valid), '%P')
		def makeLabelEntry(frame, labelText, entryVariable, *args, **kwargs):
			f = Frame(frame)
			Label(f, text=labelText, font=DROFrame.dro_mpos).pack(side=LEFT, fill=X)
			e = Entry(f, width=4, textvariable=entryVariable, validate='all', validatecommand=vcmd)
			e.pack(side=LEFT, fill=X, expand=TRUE)
			e.bind("<Return>", lambda x, s=self: s.focus_set())
			f.pack(*args, **kwargs) #side=TOP, fill=X, expand=TRUE)

		baseFrame = Frame(frame)
		lFrame = Frame(baseFrame)
		rFrame = Frame(baseFrame)
		f = Frame(lFrame)
		Label(f, text="Configuração da Rosca.", font=DROFrame.dro_mpos).pack(side=LEFT, fill=X)
		f.pack(side=TOP, fill=X, expand=TRUE)

		makeLabelEntry(lFrame, "Ferramenta de rosca:", self.info.tool, side=TOP, fill=X, expand=TRUE)
		makeLabelEntry(lFrame, "Tempo de espera após M3:", self.info.m3Wait, side=TOP, fill=X, expand=TRUE)
		makeLabelEntry(lFrame, "Passo da rosca:", self.info.pitch, side=TOP, fill=X, expand=TRUE)
		makeLabelEntry(lFrame, "Profundidade Total da rosca:", self.info.depth, side=TOP, fill=X, expand=TRUE)
		makeLabelEntry(lFrame, "Incremento de profundidade por passe:", self.info.depthIncrementPerPass, side=TOP, fill=X, expand=TRUE)
		makeLabelEntry(lFrame, "Degressão de profundidade por passe:", self.info.depthDegression, side=TOP, fill=X, expand=TRUE)
		makeLabelEntry(lFrame, "RPM do eixo Arvore:", self.info.rpm, side=TOP, fill=X, expand=TRUE)

		makeLabelEntry(rFrame, "Posição inicial do eixo Z", self.info.startZ, side=TOP, fill=X, expand=TRUE)
		makeLabelEntry(rFrame, "Posição final do eixo Z", self.info.endZ, side=TOP, fill=X, expand=TRUE)
		makeLabelEntry(rFrame, "Posição inicial do eixo X", self.info.startX, side=TOP, fill=X, expand=TRUE)
		makeLabelEntry(rFrame, "Posição do inicio da rosca no eixo X:", self.info.beginThreadCutOnX, side=TOP, fill=X, expand=TRUE)
		makeLabelEntry(rFrame, "Distância do chanfro:", self.info.taperDistance, side=TOP, fill=X, expand=TRUE)
		f = Frame(rFrame)
		Label(f, text="Chanfro inicial/final:", font=DROFrame.dro_mpos).pack(side=LEFT, fill=X)
		e = Checkbutton(f, variable=self.info.entryTaper)
		e.pack(side=LEFT, fill=X, expand=TRUE)
		e = Checkbutton(f, variable=self.info.exitTaper)
		e.pack(side=LEFT, fill=X, expand=TRUE)
		f.pack(side=TOP, fill=X, expand=TRUE)
		makeLabelEntry(rFrame, "Passes de acabamento:", self.info.springPasses, side=TOP, fill=X, expand=TRUE)
		makeLabelEntry(rFrame, "Angulo de ajuste:", self.info.slideAngle, side=TOP, fill=X, expand=TRUE)

		lFrame.pack(side=LEFT, fill=BOTH, expand=FALSE)
		rFrame.pack(side=LEFT,fill=BOTH, expand=FALSE)
		baseFrame.pack(side=TOP, fill=BOTH, expand=FALSE)
		self.text = Text(frame, width=70, height=8, state='disabled', font=DROFrame.dro_wpos)
		self.text.pack(side=TOP, fill=Y, expand=FALSE)


	def valid(self, future_value):
		if len(future_value)==0: return True
		if future_value == "-": return True
		try:
			float(future_value)
			return True
		except ValueError:
			return False

	def onExit(self):
		if self.myThread is not None and self.myThread.is_alive():
			self.stopThread = 1
			self.myThread.join()
		self.destroy()

	def move(self, gcode, wait=False):
		self.app.sendGCode(gcode)
		self.app.sendGCode((WAIT,))
		time.sleep(0.1)
		while self.app.sio_wait:
			time.sleep(0.01)
			if self.stopThread:
				return

	def calibrateRoutine(self):
		self.move("M3S{}".format(self.info.rpm.get()))
		if self.stopThread:
			return
		self.move("G4P2")
		if self.stopThread:
			return
		l = self.info.pitch.get()/2
		r = self.info.pitch.get() + max(10, self.info.pitch.get())
		if r*self.info.rpm.get() > 9000:
			r = 9000/self.info.rpm.get()

		def getG33(zPosition, pitch):
			return "G33Z{}K{}\n".format(zPosition, pitch)

		self.move("G0Z{}".format(self.info.startZ.get()))
		if self.stopThread:
			return

		positions = [self.info.startZ.get(),  self.info.endZ.get()]
		id = 1
		currentPitch = self.info.pitch.get()
		currentError = 1000
		for _ in range(20):
			if self.stopThread:
				return
			m = (l+r)/2
			self.move(getG33(positions[id], m), True)
			if self.stopThread:
				return
			id = not id
			if "alarm" in CNC.vars["state"].lower():
				return
			realPitch = CNC.vars["pitch"]
			if realPitch == -1:
				continue
			print("K={}; realpitch={}\n".format(m,realPitch))
			if abs(self.info.pitch.get()-realPitch) <= currentError:
				currentError = abs(self.info.pitch.get() - realPitch)
				currentPitch = m
			error = self.info.pitch.get() - realPitch
			if error <= 0:
				r = m - 0.01
			else:
				l = m + 0.01
		self.move("M5")
		if self.stopThread:
			return
		originalPitch = self.info.pitch.get()
		self.info.pitch.set(currentPitch)
		gcode = self.info.generateGCode()
		self.setText(gcode)
		self.info.pitch.set(originalPitch)

	def setText(self, text):
		self.text.configure(state='normal')
		self.text.delete("1.0", "end")
		self.text.insert('end', text)
		self.text.configure(state='disabled')

	def onCalibrate(self):
		msg = "Você deseja continuar?\nA maquina ligará o eixo arvore e se movimentará com o eixo Z da coordenada {} até a coordenada {}.".format(self.info.startZ.get(), self.info.endZ.get())
		ok = askokcancel("WARNING",msg)
		if not ok:
			return
		self.myThread = threading.Thread(target=self.calibrateRoutine)
		self.myThread.start()

	def onGenerate(self):
		self.setText(self.info.generateGCode())

	def buttonbox(self,*args):
		Button(self, text="Generate", command=self.onGenerate).pack(side=LEFT)
		Button(self, text="Calibrate", command=self.onCalibrate).pack(side=LEFT)
		Button(self, text="Exit", command=self.onExit).pack(side=LEFT)
