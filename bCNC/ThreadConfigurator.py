from tkinter import *
import tkinter
import threading
import copy
import time
from tkinter.simpledialog import Dialog
from tkinter.messagebox import askokcancel
from ControlPage import DROFrame
import Utils

from CNC import WCS, CNC

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
		baseFrame = Frame(frame)
		f = Frame(baseFrame)
		Label(f, text="Configuração da Rosca.", font=DROFrame.dro_mpos).pack(side=LEFT, fill=X)
		f.pack(side=TOP, fill=X, expand=TRUE)
		vcmd = (frame.register(self.valid), '%P')

		f = Frame(baseFrame)
		Label(f, text="Ferramenta de rosca:", font=DROFrame.dro_mpos).pack(side=LEFT)
		e = Entry(f, textvariable=self.info.tool, validate='all', validatecommand=vcmd)
		e.pack(side=LEFT, expand=TRUE, fill=X)
		e.bind("<Return>", lambda x, s=self: s.focus_set())
		f.pack(side=TOP, fill=X, expand=TRUE)
		f = Frame(baseFrame)
		Label(f, text="Tempo de espera para após ligar spindle:", font=DROFrame.dro_mpos).pack(side=LEFT)
		e = Entry(f, textvariable=self.info.m3Wait, validate='all', validatecommand=vcmd)
		e.pack(side=LEFT, expand=TRUE, fill=X)
		e.bind("<Return>", lambda x, s=self: s.focus_set())
		f.pack(side=TOP, fill=X, expand=TRUE)
		f = Frame(baseFrame)
		Label(f, text="Passo da rosca:", font=DROFrame.dro_mpos).pack(side=LEFT)
		e = Entry(f, textvariable=self.info.pitch, validate='all', validatecommand=vcmd)
		e.pack(side=LEFT, expand=TRUE, fill=X)
		e.bind("<Return>", lambda x, s=self: s.focus_set())
		f.pack(side=TOP, fill=X, expand=TRUE)
		f = Frame(baseFrame)
		Label(f, text="Profundidade Total da rosca:", font=DROFrame.dro_mpos).pack(side=LEFT)
		e = Entry(f, textvariable=self.info.depth, validate='all', validatecommand=vcmd)
		e.pack(side=LEFT, expand=TRUE, fill=X)
		e.bind("<Return>", lambda x, s=self: s.focus_set())
		f.pack(side=TOP, fill=X, expand=TRUE)
		f = Frame(baseFrame)
		Label(f, text="Incremento de profundidade por passe inicial:", font=DROFrame.dro_mpos).pack(side=LEFT)
		e = Entry(f, textvariable=self.info.depthIncrementPerPass, validate='all', validatecommand=vcmd)
		e.pack(side=LEFT, expand=TRUE, fill=X)
		e.bind("<Return>", lambda x, s=self: s.focus_set())
		f.pack(side=TOP, fill=X, expand=TRUE)
		f = Frame(baseFrame)
		Label(f, text="Degressão de profundidade por passe:", font=DROFrame.dro_mpos).pack(side=LEFT)
		e = Entry(f, textvariable=self.info.depthDegression, validate='all', validatecommand=vcmd)
		e.pack(side=LEFT, expand=TRUE, fill=X)
		e.bind("<Return>", lambda x, s=self: s.focus_set())
		f.pack(side=TOP, fill=X, expand=TRUE)
		f = Frame(baseFrame)
		Label(f, text="RPM do eixo arvore:", font=DROFrame.dro_mpos).pack(side=LEFT)
		e = Entry(f, textvariable=self.info.rpm, validate='all', validatecommand=vcmd)
		e.pack(side=LEFT, expand=TRUE, fill=X)
		e.bind("<Return>", lambda x, s=self: s.focus_set())
		f.pack(side=TOP, fill=X, expand=TRUE)
		f = Frame(baseFrame)
		Label(f, text="Posição inicial do eixo Z:", font=DROFrame.dro_mpos).pack(side=LEFT)
		e = Entry(f, textvariable=self.info.startZ, validate='all', validatecommand=vcmd)
		e.pack(side=LEFT, expand=TRUE, fill=X)
		e.bind("<Return>", lambda x, s=self: s.focus_set())
		f.pack(side=TOP, fill=X, expand=TRUE)
		f = Frame(baseFrame)
		Label(f, text="Posição final do eixo Z:", font=DROFrame.dro_mpos).pack(side=LEFT)
		e = Entry(f, textvariable=self.info.endZ, validate='all', validatecommand=vcmd)
		e.pack(side=LEFT, expand=TRUE, fill=X)
		e.bind("<Return>", lambda x, s=self: s.focus_set())
		f.pack(side=TOP, fill=X, expand=TRUE)
		f = Frame(baseFrame)
		Label(f, text="Posição inicial do eixo X:", font=DROFrame.dro_mpos).pack(side=LEFT)
		e = Entry(f, textvariable=self.info.startX, validate='all', validatecommand=vcmd)
		e.pack(side=LEFT, expand=TRUE, fill=X)
		e.bind("<Return>", lambda x, s=self: s.focus_set())
		f.pack(side=TOP, fill=X, expand=TRUE)
		f = Frame(baseFrame)
		Label(f, text="Posição do inicio da rosca no eixo X:", font=DROFrame.dro_mpos).pack(side=LEFT)
		e = Entry(f, textvariable=self.info.beginThreadCutOnX, validate='all', validatecommand=vcmd)
		e.pack(side=LEFT, expand=TRUE, fill=X)
		e.bind("<Return>", lambda x, s=self: s.focus_set())
		f.pack(side=TOP, fill=X, expand=TRUE)
		f = Frame(baseFrame)
		Label(f, text="Distância do chanfro:", font=DROFrame.dro_mpos).pack(side=LEFT)
		e = Entry(f, textvariable=self.info.taperDistance, validate='all', validatecommand=vcmd)
		e.pack(side=LEFT, expand=TRUE, fill=X)
		e.bind("<Return>", lambda x, s=self: s.focus_set())
		f.pack(side=TOP, fill=X, expand=TRUE)
		f = Frame(baseFrame)
		Label(f, text="Chanfro inicial:", font=DROFrame.dro_mpos).pack(side=LEFT)
		e = Checkbutton(f, variable=self.info.entryTaper)
		e.pack(side=LEFT, expand=TRUE, fill=X)
		f.pack(side=TOP, fill=X, expand=TRUE)
		f = Frame(baseFrame)
		Label(f, text="Chanfro final:", font=DROFrame.dro_mpos).pack(side=LEFT)
		e = Checkbutton(f, variable=self.info.exitTaper)
		e.pack(side=LEFT, expand=TRUE, fill=X)
		f.pack(side=TOP, fill=X, expand=TRUE)
		f = Frame(baseFrame)
		Label(f, text="Passes de acabamento:", font=DROFrame.dro_mpos).pack(side=LEFT)
		e = Entry(f, textvariable=self.info.springPasses, validate='all', validatecommand=vcmd)
		e.pack(side=LEFT, expand=TRUE, fill=X)
		e.bind("<Return>", lambda x, s=self: s.focus_set())
		f.pack(side=TOP, fill=X, expand=TRUE)
		f = Frame(baseFrame)
		Label(f, text="Angulo de ajuste:", font=DROFrame.dro_mpos).pack(side=LEFT)
		e = Entry(f, textvariable=self.info.slideAngle, validate='all', validatecommand=vcmd)
		e.pack(side=LEFT, expand=TRUE, fill=X)
		e.bind("<Return>", lambda x, s=self: s.focus_set())
		f.pack(side=TOP, fill=X, expand=TRUE)

		baseFrame.pack(side=LEFT, fill=Y, expand=TRUE)
		self.text = Text(frame,width=50, state='disabled', font=DROFrame.dro_wpos)
		self.text.pack(side=LEFT, fill=BOTH, expand=TRUE)


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
		timeout = 0
		while "idle" not in CNC.vars["state"].lower() and "alarm" not in CNC.vars["state"].lower():
			if self.stopThread:
				return
			time.sleep(0.1)
		self.app.sendGCode(gcode)
		if wait:
			timeout = 0
			while "run" not in CNC.vars["state"].lower():
				if self.stopThread:
					return
				time.sleep(0.01)
				timeout += 0.01
				if timeout >= 5:
					self.stopThread = 1
					return
		else:
			time.sleep(1)
		while "idle" not in CNC.vars["state"].lower() and "alarm" not in CNC.vars["state"].lower():
			if self.stopThread:
				return
			time.sleep(0.1)

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
		modifiedInfo = copy.deepcopy(self.info)
		modifiedInfo.pitch.set(currentPitch)
		gcode = modifiedInfo.generateGCode()
		self.setText(gcode)

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
