from tkinter import *
import tkinter
import threading
import Utils
import time
from tkinter.simpledialog import Dialog
from tkinter.messagebox import askokcancel
from ControlPage import DROFrame

from CNC import WCS, CNC

def generateGCode(rpm, startZ, startX, endZ, beginThreadCutOnX, pitch, depth, incrementDepth, degression, slideAngle, springPasses, entryTaper, exitTaper, taperLenght):
	gcode = ""
	gcode += "M3 S%.1f\n" % rpm
	gcode += "G0Z%.4fX%.4f\n" % (startZ, startX)
	z = endZ
	i = beginThreadCutOnX - startX
	p = pitch
	k = depth
	j = incrementDepth
	r = degression
	q = slideAngle
	h = springPasses
	l = 0
	if entryTaper:
		l += 1
	if exitTaper:
		l += 2
	e = taperLenght
	gcode += "G76 Z%.4f I%.4f P%.4f K%.4f J%.4f R%.2f Q%.2f H%d E%d L%.4f\n" % (z, i, p, k, j, r, q, h, e, l)
	gcode += "G0Z%.4fX%.4f\n" % (startZ, startX)
	return gcode
class ThreadInfo:
	def __init__(self):
		self.rpm = DoubleVar(value=1000)
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


class ThreadConfigurator(Dialog):
	def __init__(self, parent, title, app):
		self.app = app
		self.parent = parent
		self.info = ThreadInfo()
		self.text = None
		Dialog.__init__(self, parent, title)

	def body(self, frame):
		baseFrame = Frame(frame)
		f = Frame(baseFrame)
		Label(f, text="Configuração da Rosca.").pack(side=LEFT, fill=X)
		f.pack(side=TOP, fill=X, expand=TRUE)
		vcmd = (frame.register(self.valid), '%P')

		f = Frame(baseFrame)
		Label(f, text="Passo da rosca:").pack(side=LEFT)
		e = Entry(f, textvariable=self.info.pitch, validate='all', validatecommand=vcmd)
		e.pack(side=LEFT, expand=TRUE, fill=X)
		e.bind("<Return>", lambda x, s=self: s.focus_set())
		f.pack(side=TOP, fill=X, expand=TRUE)
		f = Frame(baseFrame)
		Label(f, text="Profundidade Total da rosca:").pack(side=LEFT)
		e = Entry(f, textvariable=self.info.depth, validate='all', validatecommand=vcmd)
		e.pack(side=LEFT, expand=TRUE, fill=X)
		e.bind("<Return>", lambda x, s=self: s.focus_set())
		f.pack(side=TOP, fill=X, expand=TRUE)
		f = Frame(baseFrame)
		Label(f, text="Incremento de profundidade por passe inicial:").pack(side=LEFT)
		e = Entry(f, textvariable=self.info.depthIncrementPerPass, validate='all', validatecommand=vcmd)
		e.pack(side=LEFT, expand=TRUE, fill=X)
		e.bind("<Return>", lambda x, s=self: s.focus_set())
		f.pack(side=TOP, fill=X, expand=TRUE)
		f = Frame(baseFrame)
		Label(f, text="Degressão de profundidade por passe:").pack(side=LEFT)
		e = Entry(f, textvariable=self.info.depthDegression, validate='all', validatecommand=vcmd)
		e.pack(side=LEFT, expand=TRUE, fill=X)
		e.bind("<Return>", lambda x, s=self: s.focus_set())
		f.pack(side=TOP, fill=X, expand=TRUE)
		f = Frame(baseFrame)
		Label(f, text="RPM do eixo arvore:").pack(side=LEFT)
		e = Entry(f, textvariable=self.info.rpm, validate='all', validatecommand=vcmd)
		e.pack(side=LEFT, expand=TRUE, fill=X)
		e.bind("<Return>", lambda x, s=self: s.focus_set())
		f.pack(side=TOP, fill=X, expand=TRUE)
		f = Frame(baseFrame)
		Label(f, text="Posição inicial do eixo Z:").pack(side=LEFT)
		e = Entry(f, textvariable=self.info.startZ, validate='all', validatecommand=vcmd)
		e.pack(side=LEFT, expand=TRUE, fill=X)
		e.bind("<Return>", lambda x, s=self: s.focus_set())
		f.pack(side=TOP, fill=X, expand=TRUE)
		f = Frame(baseFrame)
		Label(f, text="Posição final do eixo Z:").pack(side=LEFT)
		e = Entry(f, textvariable=self.info.endZ, validate='all', validatecommand=vcmd)
		e.pack(side=LEFT, expand=TRUE, fill=X)
		e.bind("<Return>", lambda x, s=self: s.focus_set())
		f.pack(side=TOP, fill=X, expand=TRUE)
		f = Frame(baseFrame)
		Label(f, text="Posição inicial do eixo X:").pack(side=LEFT)
		e = Entry(f, textvariable=self.info.startX, validate='all', validatecommand=vcmd)
		e.pack(side=LEFT, expand=TRUE, fill=X)
		e.bind("<Return>", lambda x, s=self: s.focus_set())
		f.pack(side=TOP, fill=X, expand=TRUE)
		f = Frame(baseFrame)
		Label(f, text="Posição do inicio da rosca no eixo X:").pack(side=LEFT)
		e = Entry(f, textvariable=self.info.beginThreadCutOnX, validate='all', validatecommand=vcmd)
		e.pack(side=LEFT, expand=TRUE, fill=X)
		e.bind("<Return>", lambda x, s=self: s.focus_set())
		f.pack(side=TOP, fill=X, expand=TRUE)
		f = Frame(baseFrame)
		Label(f, text="Distância do chanfro:").pack(side=LEFT)
		e = Entry(f, textvariable=self.info.taperDistance, validate='all', validatecommand=vcmd)
		e.pack(side=LEFT, expand=TRUE, fill=X)
		e.bind("<Return>", lambda x, s=self: s.focus_set())
		f.pack(side=TOP, fill=X, expand=TRUE)
		f = Frame(baseFrame)
		Label(f, text="Chanfro inicial:").pack(side=LEFT)
		e = Checkbutton(f, variable=self.info.entryTaper)
		e.pack(side=LEFT, expand=TRUE, fill=X)
		f.pack(side=TOP, fill=X, expand=TRUE)
		f = Frame(baseFrame)
		Label(f, text="Chanfro final:").pack(side=LEFT)
		e = Checkbutton(f, variable=self.info.exitTaper)
		e.pack(side=LEFT, expand=TRUE, fill=X)
		f.pack(side=TOP, fill=X, expand=TRUE)
		f = Frame(baseFrame)
		Label(f, text="Passes de acabamento:").pack(side=LEFT)
		e = Entry(f, textvariable=self.info.springPasses, validate='all', validatecommand=vcmd)
		e.pack(side=LEFT, expand=TRUE, fill=X)
		e.bind("<Return>", lambda x, s=self: s.focus_set())
		f.pack(side=TOP, fill=X, expand=TRUE)
		f = Frame(baseFrame)
		Label(f, text="Angulo de ajuste:").pack(side=LEFT)
		e = Entry(f, textvariable=self.info.slideAngle, validate='all', validatecommand=vcmd)
		e.pack(side=LEFT, expand=TRUE, fill=X)
		e.bind("<Return>", lambda x, s=self: s.focus_set())
		f.pack(side=TOP, fill=X, expand=TRUE)

		baseFrame.pack(side=LEFT, fill=BOTH, expand=TRUE)
		self.text = Text(frame,width=50, state='disabled')
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
		self.destroy()
	def move(self, gcode, wait=False):
		while CNC.vars["planner"] < 100:
			time.sleep(0.1)
		self.app.sendGCode(gcode)
		if wait:
			while "run" not in CNC.vars["state"].lower():
				time.sleep(0.01)
		else:
			time.sleep(1)
		while "idle" not in CNC.vars["state"].lower() and "alarm" not in CNC.vars["state"].lower():
			time.sleep(0.1)

	def calibrateRoutine(self):
		self.move("M3S{}".format(self.info.rpm.get()))
		self.move("G4P2")
		l = self.info.pitch.get()/2
		r = self.info.pitch.get() + max(10, self.info.pitch.get())
		if r*self.info.rpm.get() > 9000:
			r = 9000/self.info.rpm.get()

		def getG33(zPosition, pitch):
			return "G33Z{}K{}\n".format(zPosition, pitch)

		self.move("G0Z{}".format(self.info.startZ.get()))

		positions = [self.info.startZ.get(),  self.info.endZ.get()]
		id = 1
		currentPitch = self.info.pitch.get()
		currentError = 1000
		for _ in range(20):
			m = (l+r)/2
			self.move(getG33(positions[id], m), True)
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

		gcode = generateGCode(self.info.rpm.get(),
							  self.info.startZ.get(),
							  self.info.startX.get(),
							  self.info.endZ.get(),
							  self.info.beginThreadCutOnX.get(),
							  currentPitch,
							  self.info.depth.get(),
							  self.info.depthIncrementPerPass.get(),
							  self.info.depthDegression.get(),
							  self.info.slideAngle.get(),
							  self.info.springPasses.get(),
							  self.info.entryTaper.get(),
							  self.info.exitTaper.get(),
							  self.info.taperDistance.get())
		self.text.configure(state='normal')
		self.text.delete("1.0", "end")
		self.text.insert('end', gcode)
		self.text.configure(state='disabled')

	def onCalibrate(self):
		msg = "Você deseja continuar?\nA maquina ligará o eixo arvore e se movimentará com o eixo Z da coordenada {} até a coordenada {}.".format(self.info.startZ.get(), self.info.endZ.get())
		ok = askokcancel("WARNING",msg)
		if not ok:
			return
		threading.Thread(target=self.calibrateRoutine).start()


	def buttonbox(self,*args):
		Button(self, text="Calibrate", command=self.onCalibrate).pack(side=LEFT)
		Button(self, text="Exit", command=self.onExit).pack(side=LEFT)
