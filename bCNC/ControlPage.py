# -*- coding: ascii -*-
# $Id$
#
# Author: vvlachoudis@gmail.com
# Date: 18-Jun-2015

from __future__ import absolute_import
from __future__ import print_function
__author__ = "Vasilis Vlachoudis"
__email__  = "vvlachoudis@gmail.com"

try:
	import Tkinter
	from Tkinter import *
	import tkMessageBox 
	from Tkinter.simpledialog import Dialog, askfloat, askinteger
except ImportError:
	import tkinter
	from tkinter import *
	import tkinter.messagebox as tkMessageBox
	from tkinter.simpledialog import Dialog, askfloat, askinteger

import tkinter.ttk as ttk
import math
from math import * #Math in DRO

from CNCRibbon import Page
from CNC import CNC
import functools
import Utils
import Ribbon
import Sender
import tkExtra
import Unicode
import CNCRibbon
from Sender import ERROR_CODES
from CNC import WCS, DISTANCE_MODE, FEED_MODE, UNITS, PLANE

import GCodeViewer
import PidLog
import CNCCanvas

_LOWSTEP   = 0.0001
_HIGHSTEP  = 1000.0
_HIGHZSTEP = 10.0
_LOWFEED   = 10
_HIGHFEED  = 10000
_NOZSTEP = 'XY'
_HIGHASTEP = 90.0
_NOASTEP = 'BC'

OVERRIDES = ["Feed", "Rapid", "Spindle"]


#===============================================================================
# Connection Group
#===============================================================================
class ConnectionGroup(CNCRibbon.ButtonMenuGroup):
	def __init__(self, master, app):
		CNCRibbon.ButtonMenuGroup.__init__(self, master, N_("Connection"), app,
			[(_("Hard Reset"),  "reset",     app.hardReset) ])
		self.grid2rows()

		# ---
		col,row=0,0
		b = Ribbon.LabelButton(self.frame,
				image=Utils.icons["home32"],
				text=_("Home"),
				compound=TOP,
				anchor=W,
				command=app.home,
				background=Ribbon._BACKGROUND)
		b.grid(row=row, column=col, rowspan=3, padx=0, pady=0, sticky=NSEW)
		tkExtra.Balloon.set(b, _("Perform a homing cycle [$H] now"))
		self.addWidget(b)

		# ---
		col,row=1,0
		b = Ribbon.LabelButton(self.frame,
				image=Utils.icons["unlock"],
				text=_("Unlock/Startup"),
				compound=LEFT,
				anchor=W,
				command=app.softReset,
				background=Ribbon._BACKGROUND)
		b.grid(row=row, column=col, padx=0, pady=0, rowspan=2, sticky=NSEW)
		tkExtra.Balloon.set(b, _("Unlock controller [$X]"))
		self.addWidget(b)


#===============================================================================
# User Group
#===============================================================================
class UserGroup(CNCRibbon.ButtonGroup):
	def __init__(self, master, app):
		CNCRibbon.ButtonGroup.__init__(self, master, "User", app)
		self.grid3rows()

		n = Utils.getInt("Buttons","n",7)
		for i in range(1,n):
			b = Utils.UserButton(self.frame, self.app, i,
					anchor=W,
					background=Ribbon._BACKGROUND)
			col,row = divmod(i-1,3)
			b.grid(row=row, column=col, sticky=NSEW)
			self.addWidget(b)

class SetCompensationDialog(Dialog):
	def __init__(self, parent, title, app):
		self.app = app
		self.compensation = self.app.compensationTable
		self.compensationTable = self.app.compensationTable.getTable()
		self.tool = StringVar(value="1")
		self.axes = Utils.getStr("CNC", "axis", "XYZABC").lower()
		self.var = [StringVar(value='0'), StringVar(value='0'),
				StringVar(value='0'), StringVar(value='0'),
				StringVar(value='0'), StringVar(value='0')]
		Dialog.__init__(self, parent, title)

	def body(self, frame):
		f = Frame(frame)
		Label(f, text="Compensate TOOL").pack(side=LEFT, fill=X)
		cb = Label(f, textvariable=self.tool, font=DROFrame.dro_wpos)
		cb.pack(side=RIGHT)
		self.tool.set(CNC.vars["tool"])
		f.pack(side=TOP, fill=X, expand=TRUE)

		f = Frame(frame)
		vcmd = (self.parent.register(self.valid), '%P')
		for (id,w) in enumerate(self.axes):
			f2 = Frame(f)
			Label(f2, text=w).pack(side=LEFT, fill=X)
			e = Entry(f2, textvariable=self.var[id], validate='all', validatecommand=vcmd)
			e.pack(side=LEFT, expand=TRUE, fill=X)
			e.bind("<Return>", lambda x, s=self: s.focus_set())

			b = Button(f2, text="Zero", command=functools.partial(self.zero, self.var[id]))
			b.pack(side=RIGHT, fill=X)
			f2.pack(side=TOP, fill=X, expand=TRUE)
		f.pack(side=TOP, fill=BOTH, expand=TRUE)

		self.onLoadTable()

	def zero(self, strVar: StringVar):
		strVar.set("0.00")

	def newCompensation(self, index):
		return {'index':index, 'x':0, 'y':0,'z':0,'a':0,'b':0,'c':0}

	def getCompensationFromTable(self, index):
		comp, id = self.compensation.getRow(index)
		if id==-1:
			self.compensationTable.append(self.newCompensation(index))
		return self.compensationTable[id]

	def onLoadTable(self, *args):
		index = int(self.tool.get())
		tool = self.getCompensationFromTable(index)
		for (id, w) in enumerate(self.axes):
			self.var[id].set("%.03f" % float(tool[w]))

	def valid(self, future_value):
		if len(future_value)==0: return True
		if future_value == "-": return True
		try:
			float(future_value)
			return True
		except ValueError:
			return False

	def getCompensationFromScreen(self):
		values = {}
		for (id, w) in enumerate(self.axes):
			s = self.var[id].get()
			if s=="" or s=="-": # only cornerCases not treated
				s = "0"
			values[w.lower()] = float(s)
		return values 

	def onOk(self):
		index = int(self.tool.get())
		compensate = self.getCompensationFromScreen()
		self.app.mcontrol._toolCompensate(index, **compensate)
		self.app.unlock()

	def onExit(self):
		self.destroy()

	def buttonbox(self,*args):
		Button(self, text="Ok", command=self.onOk).pack(side=RIGHT)
		Button(self, text="Exit", command=self.onExit).pack(side=LEFT)

class SetToolZeroDialog(Dialog):
	def __init__(self, parent, title, app):
		self.app = app
		self.tool = self.app.toolTable
		self.toolTable = self.app.toolTable.getTable()
		self.workTable = self.app.workTable
		self.wcs = 1
		self.toolNumber = StringVar(value="1")
		self.axes = Utils.getStr("CNC", "axis", "XYZABC").lower()
		self.var = [StringVar(value='0'), StringVar(value='0'),
				StringVar(value='0'), StringVar(value='0'),
				StringVar(value='0'), StringVar(value='0')]
		Dialog.__init__(self, parent, title)

	def body(self, frame):
		f = Frame(frame)
		Label(f, text="TOOL").pack(side=LEFT, fill=X)
		cb = Label(f, textvariable=self.toolNumber, font=DROFrame.dro_wpos)
		cb.pack(side=RIGHT)
		self.toolNumber.set(CNC.vars["tool"])
		self.wcs = WCS.index(CNC.vars["WCS"])+1
		f.pack(side=TOP, fill=X, expand=TRUE)

		f = Frame(frame)
		vcmd = (self.parent.register(self.valid), '%P')
		for (id,w) in enumerate(self.axes):
			f2 = Frame(f)
			Label(f2, text=w).pack(side=LEFT, fill=X)
			e = Entry(f2, textvariable=self.var[id], validate='all', validatecommand=vcmd)
			e.pack(side=LEFT, expand=TRUE, fill=X)
			e.bind("<Return>", lambda x, s=self: s.focus_set())

			b = Button(f2, text="Zero", command=functools.partial(self.zero, self.var[id]))
			b.pack(side=RIGHT, fill=X)
			f2.pack(side=TOP, fill=X, expand=TRUE)
		f.pack(side=TOP, fill=BOTH, expand=TRUE)

		if Utils.getBool("CNC", "lathe", False):
			f = Frame(frame)
			if 'x' in self.axes:
				Button(f, text="X Diameter", command=functools.partial(self.enterDiameter,'x', f)).pack(side=LEFT, fill=BOTH, expand=TRUE)
			if 'b' in self.axes:
				Button(f, text="B Diameter", command=functools.partial(self.enterDiameter,'b', f)).pack(side=LEFT, fill=BOTH, expand=TRUE)
			f.pack(side=TOP, fill=BOTH, expand=TRUE)

		self.onLoadTable()

	def enterDiameter(self, axis, frame, *args):
		if axis not in self.axes:
			return
		id = self.axes.index(axis)
		self.var[id].set("%.03f" % askfloat("{} Diameter set".format(axis), "Diameter measured",
					parent=frame,
					minvalue=-100000.0, maxvalue=100000.0))

	def zero(self, strVar: StringVar):
		strVar.set("0.00")

	def newTool(self, index):
		return {'index':index, 'x':0, 'y':0,'z':0,'a':0,'b':0,'c':0}

	def getTool(self, index):
		tool, id = self.tool.getRow(index)
		if id==-1:
			self.toolTable.append(self.newTool(index))
		return self.toolTable[id]

	def onLoadTable(self, *args):
		index = int(self.toolNumber.get())
		tlo = self.getTool(index)
		wcs, id = self.workTable.getRow(self.wcs)
		for (id, w) in enumerate(self.axes):
			self.var[id].set("%.03f" % float(float(CNC.vars["m"+w]) - float(tlo[w]) - float(wcs[w])))

	def valid(self, future_value):
		if len(future_value)==0: return True
		if future_value == "-": return True
		try:
			float(future_value)
			return True
		except ValueError:
			return False

	def getTlo(self):
		values = {}
		for (id, w) in enumerate(self.axes):
			s = self.var[id].get()
			if s=="" or s=="-": # only cornerCases not treated
				s = "0"
			values[w.lower()] = float(s)
		return values 

	def onOk(self):
		index = int(self.toolNumber.get())
		tlo = self.getTlo()
		wcs, id = self.workTable.getRow(self.wcs)
		for axe in self.axes:
			tlo[axe] = float(CNC.vars['m{}'.format(axe)]) - tlo[axe] - float(wcs[axe])
		self.app.mcontrol._tloSet(index, **tlo)
		self.app.unlock()

	def onExit(self):
		self.destroy()

	def buttonbox(self,*args):
		Button(self, text="Ok", command=self.onOk).pack(side=RIGHT)
		Button(self, text="Exit", command=self.onExit).pack(side=LEFT)

class SetWorkZeroDialog(Dialog):
	def __init__(self, parent, title, app):
		self.app = app
		self.wcs = StringVar(value="G54")
		self.axes = Utils.getStr("CNC", "axis", "XYZABC").lower()
		#if Utils.getBool("CNC", "lathe", False):
		#	self.axes = [w for w in self.axes if w in "z"]
		self.var = [StringVar(value='0'), StringVar(value='0'),
				StringVar(value='0'), StringVar(value='0'),
				StringVar(value='0'), StringVar(value='0')]
		Dialog.__init__(self, parent, title)
	def body(self, frame):
		f = Frame(frame)
		Label(f, text="WCS").pack(side=LEFT, fill=X)
		cb = Label(f, textvariable=self.wcs, font=DROFrame.dro_wpos)
		cb.pack(side=RIGHT)

		self.wcs.set(CNC.vars['WCS'])
		f.pack(side=TOP, fill=X, expand=TRUE)

		f = Frame(frame)
		f.pack(side=TOP, fill=X, expand=TRUE)

		f = Frame(frame)
		vcmd = (self.parent.register(self.valid), '%P')
		for (id,w) in enumerate(self.axes):
			f2 = Frame(f)
			Label(f2, text=w).pack(side=LEFT, fill=X)
			e = Entry(f2, textvariable=self.var[id], validate='all', validatecommand=vcmd)
			e.pack(side=LEFT, expand=TRUE, fill=X)
			e.bind("<Return>", lambda x, s=self: s.focus_set())

			b = Button(f2, text="Zero", command=functools.partial(self.zero, self.var[id]))
			b.pack(side=RIGHT, fill=X)
			f2.pack(side=TOP, fill=X, expand=TRUE)
		f.pack(side=TOP, fill=BOTH, expand=TRUE)
		self.onWcs() # ComboboxSelected not trigger

	def zero(self, strVar: StringVar):
		strVar.set("0.00")

	def onWcs(self, *args):
		for (id, w) in enumerate(self.axes):
			self.var[id].set("%.03f" % float(CNC.vars["w"+w]))

	def valid(self, future_value):
		if len(future_value)==0: return True
		if future_value == "-": return True
		try:
			float(future_value)
			return True
		except ValueError:
			return False

	def getWco(self):
		values = {}
		for (id, w) in enumerate(self.axes):
			s = self.var[id].get()
			if s=="" or s=="-": # only cornerCases not treated
				s = "0"
			values[w.lower()] = float(s)
		return values 

	def onOk(self):
		index = WCS.index(self.wcs.get())
		wco = self.getWco()
		self.app.mcontrol._wcsSet(**wco, wcsIndex=index)
		self.app.unlock()

	def onExit(self):
		self.destroy()

	def onClearTable(self):
		response = tkMessageBox.askokcancel("Clear table warning", "Do you want to continue?")
		if not response:
			return
		table = self.app.workTable
		rows = table.getTable()
		allAxis = "xyzabcuvw"
		for row in rows:
			for (field, value) in row.items():
				if field in allAxis:
					row[field] = '0'
		table.save(rows)
		self.app.unlock()
		self.destroy()


	def buttonbox(self,*args):
		Button(self, text="Ok", command=self.onOk).pack(side=RIGHT, fill=X, expand=True)
		Button(self, text="ClearTable", command=self.onClearTable).pack(side=RIGHT, fill=X, expand=True)
		Button(self, text="Exit", command=self.onExit).pack(side=RIGHT, fill=X, expand=True)


class ZeroGroup(CNCRibbon.ButtonGroup):
	def __init__(self, master, app):
		CNCRibbon.ButtonGroup.__init__(self, master, "Zero", app)
		self.master = master
		b = Ribbon.LabelButton(self.frame, self, "<<SetWorkOffset>>",
				image=Utils.icons["WCS"],
				text=_("Set Work Offset"),
				compound=TOP,
				background=Ribbon._BACKGROUND)
		b.pack(side=LEFT, fill=BOTH)
		tkExtra.Balloon.set(b, _("Set your WCS"))
		self.addWidget(b)
		b = Ribbon.LabelButton(self.frame, self, "<<SetToolOffset>>",
				image=Utils.icons["TOOL"],
				text=_("Set Tool Offset"),
				compound=TOP,
				background=Ribbon._BACKGROUND)
		b.pack(side=LEFT, fill=BOTH)
		tkExtra.Balloon.set(b, _("Set your TLO"))
		self.addWidget(b)
		b = Ribbon.LabelButton(self.frame, self, "<<SetCompensationOffset>>",
				image=Utils.icons["COMPENSATE"],
				text=_("Set Compensation"),
				compound=TOP,
				background=Ribbon._BACKGROUND)
		b.pack(side=LEFT, fill=BOTH)
		tkExtra.Balloon.set(b, _("Set your Compensation"))
		self.addWidget(b)

		app.bind("<<SetWorkOffset>>", self.onWorkClick)
		app.bind("<<SetToolOffset>>", self.onToolClick)
		app.bind("<<SetCompensationOffset>>", self.onCompensationClick)

	def onWorkClick(self, *args):
		SetWorkZeroDialog(self.app, "Set WorkSystem", self.app)
	def onToolClick(self, *args):
		SetToolZeroDialog(self.app, "Set Tool", self.app)
	def onCompensationClick(self, *args):
		SetCompensationDialog(self.app, "Set Compensation", self.app)


class StartLineDialog(Dialog):
	def __init__(self, parent, title, app, lineNumberVariable):
		self.app = app
		self.parent = parent
		self.lineNumber = lineNumberVariable
		Dialog.__init__(self, parent, title)
	def body(self, frame):
		vcmd = (frame.register(self.valid), '%P')
		def makeLabelEntry(frame, labelText, entryVariable, *args, **kwargs):
			f = Frame(frame)
			Label(f, text=labelText, font=DROFrame.dro_mpos).pack(side=LEFT, fill=X)
			e = Entry(f, width=9, textvariable=entryVariable, validate='all', validatecommand=vcmd)
			e.pack(side=LEFT, fill=X, expand=TRUE)
			e.bind("<Return>", lambda x, s=self: s.focus_set())
			f.pack(*args, **kwargs) #side=TOP, fill=X, expand=TRUE)

		makeLabelEntry(frame, "Linha de inicio: ", self.lineNumber, side=TOP, fill=BOTH, expand=TRUE)

	def onExit(self):
		CNC.vars["beginLine"] = self.lineNumber.get()
		self.destroy()

	def buttonbox(self,*args):
		Button(self, text="Exit", command=self.onExit).pack(side=LEFT)

	def valid(self, future_value):
		if len(future_value)==0: return True
		try:
			float(future_value)
			return True
		except ValueError:
			return False

class RepeatEngineConfigureDialog(Dialog):
	def __init__(self, parent, title, app):
		self.app = app
		self.engine = self.app.gcode.repeatEngine
		self.parent = parent
		Dialog.__init__(self, parent, title)
	def body(self, frame):
		vcmd = (frame.register(self.valid), '%P')
		def makeLabelEntry(frame, labelText, entryVariable, *args, **kwargs):
			f = Frame(frame)
			Label(f, text=labelText, font=DROFrame.dro_mpos).pack(side=LEFT, fill=X)
			e = Entry(f, width=9, textvariable=entryVariable, validate='all', validatecommand=vcmd)
			e.pack(side=LEFT, fill=X, expand=TRUE)
			e.bind("<Return>", lambda x, s=self: s.focus_set())
			f.pack(*args, **kwargs) #side=TOP, fill=X, expand=TRUE)

		makeLabelEntry(frame, "Numero atual de execucoes: ", self.engine.m30Counter, side=TOP, fill=BOTH, expand=TRUE)
		makeLabelEntry(frame, "Numero final de execucoes: ", self.engine.m30CounterLimit, side=TOP, fill=BOTH, expand=TRUE)

	def onExit(self):
		self.destroy()

	def buttonbox(self,*args):
		Button(self, text="Exit", command=self.onExit).pack(side=LEFT)

	def valid(self, future_value):
		if len(future_value)==0: return True
		try:
			float(future_value)
			return True
		except ValueError:
			return False
#===============================================================================
# Run Group
#===============================================================================
class RunGroup(CNCRibbon.ButtonGroup):
	def __init__(self, master, app):
		CNCRibbon.ButtonGroup.__init__(self, master, "Run", app)

		b = Ribbon.LabelButton(self.frame, self, "<<RunBegin>>",
				image=Utils.icons["start32"],
				text=_("Start"),
				compound=TOP,
				background=Ribbon._BACKGROUND)
		b.pack(side=LEFT, fill=BOTH)
		tkExtra.Balloon.set(b, _("Run g-code commands from editor to controller"))
		self.addWidget(b)

		b = Ribbon.LabelButton(self.frame, self, "<<Pause>>",
				image=Utils.icons["pause32"],
				text=_("Pause"),
				compound=TOP,
				background=Ribbon._BACKGROUND)
		b.pack(side=LEFT, fill=BOTH)
		tkExtra.Balloon.set(b, _("Pause running program. Sends either FEED_HOLD ! or CYCLE_START ~"))

		b = Ribbon.LabelButton(self.frame, self, "<<Stop>>",
				image=Utils.icons["stop32"],
				text=_("Stop"),
				compound=TOP,
				background=Ribbon._BACKGROUND)
		b.pack(side=LEFT, fill=BOTH)
		tkExtra.Balloon.set(b, _("Pause running program and soft reset controller to empty the buffer."))


		f = Frame(self.frame)
		self.lineNumber = IntVar(value=0)
		b = Ribbon.LabelButton(f, self, "<<LineNumberToStart>>",
				image=Utils.icons["edit"],
				text=_("Linha de Inicio"),
				compound=TOP,
				background=Ribbon._BACKGROUND)
		b.pack(side=TOP, fill=BOTH)
		f2 = Frame(f)
		Label(f2, text="Linha: ", font=("Sans", "-14")).pack(side=LEFT, fill=BOTH)
		Label(f2, textvariable=self.lineNumber, font=("Sans", "-14")).pack(side=LEFT, fill=BOTH)
		f2.pack(side=TOP,expand=TRUE)
		f.pack(side=LEFT, fill=BOTH)
		self.addWidget(b)
		tkExtra.Balloon.set(b, _("Linha de inicio"))
		self.app.bind("<<LineNumberToStart>>", self.onLineNumberClicked)


		f = Frame(self.frame)
		b = Ribbon.LabelButton(f, self, "<<RepeatEngineConfigure>>",
				image=Utils.icons["edit"],
				text=_("Repeticoes"),
				compound=TOP,
				background=Ribbon._BACKGROUND)
		b.pack(side=TOP, fill=BOTH)
		f2 = Frame(f)
		Label(f2, textvariable=self.app.gcode.repeatEngine.m30Counter, font=("Sans", "-14")).pack(side=LEFT, fill=BOTH)
		Label(f2, text="/", font=("Sans", "-14")).pack(side=LEFT, fill=BOTH)
		Label(f2, textvariable=self.app.gcode.repeatEngine.m30CounterLimit, font=("Sans", "-14")).pack(side=LEFT, fill=BOTH)
		f2.pack(side=TOP,expand=TRUE)
		f.pack(side=LEFT, fill=BOTH)
		tkExtra.Balloon.set(b, _("Repeticoes"))
		self.app.bind("<<RepeatEngineConfigure>>", self.onRepeatEngineConfigureClicked)

	def onLineNumberClicked(self, *args):
		StartLineDialog(self.frame, "Linha de inicio", self.master, self.lineNumber)

	def onRepeatEngineConfigureClicked(self, *args):
		RepeatEngineConfigureDialog(self.frame, "Configuracao de Repeticoes", self.app)

#===============================================================================
# DRO Frame
#===============================================================================
class DROFrame(CNCRibbon.PageFrame):
	dro_status = ('Helvetica',16,'bold')
	dro_wpos   = ('Helvetica',16,'bold')
	dro_mpos   = ('Helvetica',16)

	def __init__(self, master, app):
		CNCRibbon.PageFrame.__init__(self, master, "DRO", app)
		self.isLathe = Utils.getBool("CNC","lathe",False)
		self.axis = Utils.getStr("CNC", "axis", "XYZ")

		DROFrame.dro_status = Utils.getFont("dro.status", DROFrame.dro_status)
		DROFrame.dro_wpos   = Utils.getFont("dro.wpos",   DROFrame.dro_wpos)
		DROFrame.dro_mpos   = Utils.getFont("dro.mpos",   DROFrame.dro_mpos)
		f = Frame(self)
		f2 = Frame(f)
		Label(f2,text=_("Status:")).pack(side=LEFT, fill=X, expand=FALSE)
		self.state = Button(f2,
				text=Sender.NOT_CONNECTED,
				font=DROFrame.dro_status,
				command=self.showState,
				cursor="hand1",
				background=Sender.STATECOLOR[Sender.NOT_CONNECTED],
				activebackground="LightYellow")
		self.state.pack(side=RIGHT, fill=X, expand=TRUE)
		tkExtra.Balloon.set(self.state,
				_("Show current state of the machine\n"
				  "Click to see details\n"
				  "Right-Click to clear alarm/errors"))
		#self.state.bind("<Button-3>", lambda e,s=self : s.event_generate("<<AlarmClear>>"))
		self.state.bind("<Button-3>", self.stateMenu)

		f2.pack(side=TOP, fill=X, expand=TRUE)

		self.works = []
		self.machs = []
		f2 = Frame(f)
		Label(f2, text="Machine").pack(side=RIGHT, fill=X,expand=TRUE)
		Label(f2, text="Work").pack(side=RIGHT, fill=X, expand=TRUE)
		f2.pack(side=TOP, fill=X, expand=TRUE)
		for axe in self.axis:
			f2 = Frame(f)
			Label(f2, text=_(axe.upper()+":"), font=DROFrame.dro_wpos).pack(side=LEFT)
			mach = Label(f2, font=DROFrame.dro_mpos, background=tkExtra.GLOBAL_CONTROL_BACKGROUND,
					anchor=E,width=9)
			mach.pack(side=RIGHT, fill=X, expand=TRUE)
			tkExtra.Balloon.set(mach, _(axe+" machine position"))

			work = Label(f2, font=DROFrame.dro_wpos,
					background=tkExtra.GLOBAL_CONTROL_BACKGROUND,
					relief=RAISED, borderwidth=2, justify=RIGHT,
					width=9)
			work.pack(side=RIGHT, fill=X, expand=TRUE)
			tkExtra.Balloon.set(work, _(axe+" work position"))

			f2.pack(side=TOP, fill=X, expand=TRUE)

			self.works += [work]
			self.machs += [mach]
		f.pack(side=TOP, fill=BOTH, expand=TRUE)

	#----------------------------------------------------------------------
	def stateMenu(self, event=None):
		menu = Menu(self, tearoff=0)

		menu.add_command(label=_("Show Info"), image=Utils.icons["info"], compound=LEFT,
					command=self.showState)
		menu.add_command(label=_("Clear Message"), image=Utils.icons["clear"], compound=LEFT,
					command=lambda s=self: s.event_generate("<<AlarmClear>>"))
		menu.add_separator()

		menu.add_command(label=_("Feed hold"), image=Utils.icons["pause"], compound=LEFT,
					command=lambda s=self: s.event_generate("<<FeedHold>>"))
		menu.add_command(label=_("Resume"), image=Utils.icons["start"], compound=LEFT,
					command=lambda s=self: s.event_generate("<<Resume>>"))

		menu.tk_popup(event.x_root, event.y_root)

	#----------------------------------------------------------------------
	def updateState(self):
		msg = self.app._msg or CNC.vars["state"]
		if CNC.vars["pins"] is not None and CNC.vars["pins"] != "":
			msg += " ["+CNC.vars["pins"]+"]"
		self.state.config(text=msg, background=CNC.vars["color"])

	#----------------------------------------------------------------------
	def updateCoords(self):
		try:
			focus = self.focus_get()
		except:
			focus = None
		for (axe, work, mach) in zip(self.axis, self.works, self.machs):
			wv = "%.03f" % CNC.vars["w"+axe]
			mv = "%.03f" % CNC.vars["m"+axe]
			work["text"] = wv
			mach["text"] = mv

	#----------------------------------------------------------------------
	def padFloat(self, decimals, value):
		if decimals>0:
			return "%0.*f"%(decimals, value)
		else:
			return value

	#----------------------------------------------------------------------
	# Do not give the focus while we are running
	#----------------------------------------------------------------------
	def workFocus(self, event=None):
		if self.app.running:
			self.app.focus_set()

	#----------------------------------------------------------------------
	def showState(self):
		err = CNC.vars["errline"]
		if err:
			msg  = _("Last error: %s\n")%(CNC.vars["errline"])
		else:
			msg = ""

		state = CNC.vars["state"]
		msg += ERROR_CODES.get(state,
				_("No info available.\nPlease contact the author."))
		tkMessageBox.showinfo(_("State: %s")%(state), msg, parent=self)


#===============================================================================
# DRO Frame ABC
#===============================================================================
class abcDROFrame(CNCRibbon.PageExLabelFrame):
	dro_status = ('Helvetica',12,'bold')
	dro_wpos   = ('Helvetica',12,'bold')
	dro_mpos   = ('Helvetica',12)

	def __init__(self, master, app):
		CNCRibbon.PageExLabelFrame.__init__(self, master, "abcDRO", _("abcDRO"), app)
        
		frame = Frame(self())
		frame.pack(side=TOP, fill=X)
		
		abcDROFrame.dro_status = Utils.getFont("dro.status", abcDROFrame.dro_status)
		abcDROFrame.dro_wpos   = Utils.getFont("dro.wpos",   abcDROFrame.dro_wpos)
		abcDROFrame.dro_mpos   = Utils.getFont("dro.mpos",   abcDROFrame.dro_mpos)

		row = 0
		col = 0
		Label(frame,text=_("abcWPos:")).grid(row=row,column=col)

		# work
		col += 1
		self.awork = Entry(frame, font=abcDROFrame.dro_wpos,
					background=tkExtra.GLOBAL_CONTROL_BACKGROUND,
					width=8,
					relief=FLAT,
					borderwidth=0,
					justify=RIGHT)
		self.awork.grid(row=row,column=col,sticky=EW)
		tkExtra.Balloon.set(self.awork, _("A work position (click to set)"))
		self.awork.bind('<FocusIn>',  self.workFocus)
		self.awork.bind('<Return>',   self.setA)
		self.awork.bind('<KP_Enter>', self.setA)

		# ---
		col += 1
		self.bwork = Entry(frame, font=abcDROFrame.dro_wpos,
					background=tkExtra.GLOBAL_CONTROL_BACKGROUND,
					width=8,
					relief=FLAT,
					borderwidth=0,
					justify=RIGHT)
		self.bwork.grid(row=row,column=col,sticky=EW)
		tkExtra.Balloon.set(self.bwork, _("B work position (click to set)"))
		self.bwork.bind('<FocusIn>',  self.workFocus)
		self.bwork.bind('<Return>',   self.setB)
		self.bwork.bind('<KP_Enter>', self.setB)

		# ---
		col += 1
		self.cwork = Entry(frame, font=abcDROFrame.dro_wpos,
					background=tkExtra.GLOBAL_CONTROL_BACKGROUND,
					width=8,
					relief=FLAT,
					borderwidth=0,
					justify=RIGHT)
		self.cwork.grid(row=row,column=col,sticky=EW)
		tkExtra.Balloon.set(self.cwork, _("C work position (click to set)"))
		self.cwork.bind('<FocusIn>',  self.workFocus)
		self.cwork.bind('<Return>',   self.setC)
		self.cwork.bind('<KP_Enter>', self.setC)

		# Machine
		row += 1
		col = 0
		Label(frame,text=_("MPos:")).grid(row=row,column=col,sticky=E)

		col += 1
		self.amachine = Label(frame, font=abcDROFrame.dro_mpos, background=tkExtra.GLOBAL_CONTROL_BACKGROUND,anchor=E)
		self.amachine.grid(row=row,column=col,padx=1,sticky=EW)

		col += 1
		self.bmachine = Label(frame, font=abcDROFrame.dro_mpos, background=tkExtra.GLOBAL_CONTROL_BACKGROUND,anchor=E)
		self.bmachine.grid(row=row,column=col,padx=1,sticky=EW)

		col += 1
		self.cmachine = Label(frame, font=abcDROFrame.dro_mpos, background=tkExtra.GLOBAL_CONTROL_BACKGROUND, anchor=E)
		self.cmachine.grid(row=row,column=col,padx=1,sticky=EW)

		# Set buttons
		row += 1
		col = 1

		azero = Button(frame, text=_("A=0"),
				command=self.setA0,
				activebackground="LightYellow",
				padx=2, pady=1)
		azero.grid(row=row, column=col, pady=0, sticky=EW)
		tkExtra.Balloon.set(azero, _("Set A coordinate to zero (or to typed coordinate in WPos)"))
		self.addWidget(azero)

		col += 1
		bzero = Button(frame, text=_("B=0"),
				command=self.setB0,
				activebackground="LightYellow",
				padx=2, pady=1)
		bzero.grid(row=row, column=col, pady=0, sticky=EW)
		tkExtra.Balloon.set(bzero, _("Set B coordinate to zero (or to typed coordinate in WPos)"))
		self.addWidget(bzero)

		col += 1
		czero = Button(frame, text=_("C=0"),
				command=self.setC0,
				activebackground="LightYellow",
				padx=2, pady=1)
		czero.grid(row=row, column=col, pady=0, sticky=EW)
		tkExtra.Balloon.set(czero, _("Set C coordinate to zero (or to typed coordinate in WPos)"))
		self.addWidget(czero)

		# Set buttons
		row += 1
		col = 1
		bczero = Button(frame, text=_("BC=0"),
				command=self.setBC0,
				activebackground="LightYellow",
				padx=2, pady=1)
		bczero.grid(row=row, column=col, pady=0, sticky=EW)
		tkExtra.Balloon.set(bczero, _("Set BC coordinate to zero (or to typed coordinate in WPos)"))
		self.addWidget(bczero)

		col += 1
		abczero = Button(frame, text=_("ABC=0"),
				command=self.setABC0,
				activebackground="LightYellow",
				padx=2, pady=1)
		abczero.grid(row=row, column=col, pady=0, sticky=EW, columnspan=2)
		tkExtra.Balloon.set(abczero, _("Set ABC coordinate to zero (or to typed coordinate in WPos)"))
		self.addWidget(abczero)

		

	#----------------------------------------------------------------------
	def updateCoords(self):
		try:
			focus = self.focus_get()
		except:
			focus = None
		if focus is not self.awork:
			self.awork.delete(0,END)
			self.awork.insert(0,self.padFloat(CNC.drozeropad,CNC.vars["wa"]))
		if focus is not self.bwork:
			self.bwork.delete(0,END)
			self.bwork.insert(0,self.padFloat(CNC.drozeropad,CNC.vars["wb"]))
		if focus is not self.cwork:
			self.cwork.delete(0,END)
			self.cwork.insert(0,self.padFloat(CNC.drozeropad,CNC.vars["wc"]))

		self.amachine["text"] = self.padFloat(CNC.drozeropad,CNC.vars["ma"])
		self.bmachine["text"] = self.padFloat(CNC.drozeropad,CNC.vars["mb"])
		self.cmachine["text"] = self.padFloat(CNC.drozeropad,CNC.vars["mc"])
	#----------------------------------------------------------------------
	def padFloat(self, decimals, value):
		if decimals>0:
			return "%0.*f"%(decimals, value)
		else:
			return value

	#----------------------------------------------------------------------
	# Do not give the focus while we are running
	#----------------------------------------------------------------------
	def workFocus(self, event=None):
		if self.app.running:
			self.app.focus_set()

	#----------------------------------------------------------------------
	def setA0(self, event=None):
		self.app.mcontrol._wcsSet(None,None,None,"0",None,None)

	#----------------------------------------------------------------------
	def setB0(self, event=None):
		self.app.mcontrol._wcsSet(None,None,None,None,"0",None)

	#----------------------------------------------------------------------
	def setC0(self, event=None):
		self.app.mcontrol._wcsSet(None,None,None,None,None,"0")

	#----------------------------------------------------------------------
	def setBC0(self, event=None):
		self.app.mcontrol._wcsSet(None,None,None,"0","0",None)

	#----------------------------------------------------------------------
	def setABC0(self, event=None):
		self.app.mcontrol._wcsSet(None,None,None,"0","0","0")

	#----------------------------------------------------------------------
	def setA(self, event=None):
		if self.app.running: return
		try:
			value = round(eval(self.awork.get(), None, CNC.vars), 3)
			self.app.mcontrol._wcsSet(None,None,None,value,None,None)
		except:
			pass

	#----------------------------------------------------------------------
	def setB(self, event=None):
		if self.app.running: return
		try:
			value = round(eval(self.bwork.get(), None, CNC.vars), 3)
			self.app.mcontrol._wcsSet(None,None,None,None,value,None)
		except:
			pass

	#----------------------------------------------------------------------
	def setC(self, event=None):
		if self.app.running: return
		try:
			value = round(eval(self.cwork.get(), None, CNC.vars), 3)
			self.app.mcontrol._wcsSet(None,None,None,None,None,value)
		except:
			pass

	#----------------------------------------------------------------------
	#def wcsSet(self, x, y, z): self.app.mcontrol._wcsSet(x, y, z)

	#----------------------------------------------------------------------
	#def _wcsSet(self, x, y, z): self.app.mcontrol._wcsSet(x, y, z)

	#----------------------------------------------------------------------
	def showState(self):
		err = CNC.vars["errline"]
		if err:
			msg  = _("Last error: %s\n")%(CNC.vars["errline"])
		else:
			msg = ""

		state = CNC.vars["state"]
		msg += ERROR_CODES.get(state,
				_("No info available.\nPlease contact the author."))
		tkMessageBox.showinfo(_("State: %s")%(state), msg, parent=self)

#===============================================================================
# ToolGroup
#===============================================================================
class ToolGroup(CNCRibbon.ButtonGroup):
	def __init__(self, master, app):
		CNCRibbon.ButtonGroup.__init__(self, master, "Tool", app)
		self.master = master
		b = Ribbon.LabelButton(self.frame, self, "<<ChangeTool>>",
				image=Utils.icons["config"],
				text=_("Change Tool"),
				compound=TOP,
				background=Ribbon._BACKGROUND)
		b.pack(side=LEFT, fill=BOTH)
		tkExtra.Balloon.set(b, _("Change your tool"))
		self.addWidget(b)
		self.app.bind("<<ChangeTool>>", self.onChange)
	def onChange(self, *args):
		toolNumber = askinteger("Tool change", "Enter the tool number",
				parent=self.master,
				minvalue=0, maxvalue=10)
		self.app.sendGCode("M6T{}G43".format(toolNumber))

#===============================================================================
# MdiFrame
#===============================================================================
class MdiFrame(CNCRibbon.PageLabelFrame):
	def __init__(self, master, app):
		CNCRibbon.PageLabelFrame.__init__(self, master, "Mdi", _("Mdi"), app)
		self.master = master
		self.app = app
		f = Frame(self)
		Label(f, text="MDI:", width=5).pack(side=LEFT, fill=X)
		self.mdiVar = StringVar(value="")
		e = Entry(f, textvariable=self.mdiVar, font=DROFrame.dro_mpos)
		e.pack(side=LEFT, fill=X, expand=TRUE)
		e.bind("<Return>", self.onEnter)
		e.bind("<Up>", self.onUp)
		e.bind("<Down>", self.onDown)
		f.pack(side=TOP, fill=BOTH, expand=TRUE)
		self.values = [""]
		self.counter = 0

	def updateEntry(self):
		if self.counter >=0 and self.counter < len(self.values):
			self.mdiVar.set(self.values[self.counter])

	def onUp(self, *args):
		self.counter = max(self.counter-1,0)
		self.updateEntry()

	def onDown(self, *args):
		self.counter = min(self.counter+1,len(self.values))
		self.updateEntry()

	def onEnter(self, *args):
		if len(self.mdiVar.get())==0:
			self.app.focus_set()
		self.app.execute(self.mdiVar.get())
		self.values += [self.mdiVar.get()]
		self.mdiVar.set("")
		self.counter = len(self.values)


#===============================================================================
# ControlFrame
#===============================================================================
class ControlFrame(CNCRibbon.PageLabelFrame):
	def __init__(self, master, app):
		CNCRibbon.PageLabelFrame.__init__(self, master, "Control", _("Control"), app)
		CNC.vars["currentJogAxisNumber"] = tkinter.IntVar(value=1)
		self.isLathe = Utils.getBool("CNC","lathe",False)
		self.axis = Utils.getStr("CNC", "axis", "XYZ")
		self.crossAxis = Utils.getStr("CNC", "jogCross", "YX")
		self.jogSpeeds = []
		i = 0
		while 1:
			speed = Utils.getStr("CNC", "jogSpeed{}".format(i), "-")
			if speed == "-": break
			self.jogSpeeds += [speed]
			i += 1

		f = Frame(self)
		
		f2 = Frame(self)
		

		f3 = Frame(f2)
		b = Button(f3, text=u"\u00D710",
				command=self.mulStep,
				width=3,
				padx=1, pady=1, font="Helvetica, 14")
		b.pack(side=LEFT)
		tkExtra.Balloon.set(b, _("Multiply step by 10"))
		self.addWidget(b)
		b = Button(f3, text=_("+"),
				command=self.incStep,
				width=3,
				padx=1, pady=1, font="Helvetica, 14")
		b.pack(side=LEFT)
		tkExtra.Balloon.set(b, _("Increase step by 1 unit"))
		self.addWidget(b)

		self.step = tkExtra.Combobox(f3, width=6, background=tkExtra.GLOBAL_CONTROL_BACKGROUND, font="Helvetica, 14")
		self.step.pack(side=LEFT)
		self.step.set(Utils.config.get("Control","step"))
		self.step.fill(map(float, Utils.config.get("Control","steplist").split()))
		tkExtra.Balloon.set(self.step, _("Step for every move operation"))
		self.addWidget(self.step)

		b = Button(f3, text=_("-"),
					command=self.decStep,
					width=3,
					padx=1, pady=1, font="Helvetica, 14")
		b.pack(side=LEFT)
		tkExtra.Balloon.set(b, _("Decrease step by 1 unit"))
		self.addWidget(b)
		b = Button(f3, text=u"\u00F710",
					command=self.divStep,
					padx=1, pady=1, font="Helvetica, 14")
		b.pack(side=LEFT)
		tkExtra.Balloon.set(b, _("Divide step by 10"))
		self.addWidget(b)
		b = Button(f3, text="Ativa teclado",
				command=self.app.focus_set,
				activebackground="LightYellow")
		b.pack(side=LEFT, fill=X, padx=20)
		tkExtra.Balloon.set(b, _("Focus"))

		f3.pack(side=TOP, fill=X, expand=TRUE)

		f3 = Frame(f2)
		Label(f3, text=_("Jog Speed: "), font=DROFrame.dro_mpos).pack(side=LEFT)

		self.jogSpeedEntry = tkExtra.FloatEntry(f3, background=tkExtra.GLOBAL_CONTROL_BACKGROUND, disabledforeground="Black",width=5, font=DROFrame.dro_mpos)
		self.jogSpeedEntry.pack(side=LEFT)
		self.jogSpeedEntry.bind('<Return>',self.setJogSpeed)
		self.jogSpeedEntry.bind('<KP_Enter>',self.setJogSpeed)
		tkExtra.Balloon.set(self.jogSpeedEntry,_("Jog Speed"))
		self.addWidget(self.jogSpeedEntry)

		buttonSpeed = []
		def selectSpeed(value):
			self.jogSpeedEntry.set(value)
			self.setJogSpeed()
			self.app.focus()
		for speed in self.jogSpeeds:
			b = Button(f3, text=speed,
						width=2, height=1,
						activebackground="LightYellow",
						command=functools.partial(selectSpeed, speed),
						font=DROFrame.dro_mpos)
			b.pack(side=LEFT)
			tkExtra.Balloon.set(b, _(speed))
			self.addWidget(b)
			buttonSpeed += [b]
		f3.pack(side=TOP,fill=X, expand=TRUE)
		# A+        C+
		#    B+ crossAxis   B-
		# A-        C-


		f2.pack(side=TOP, fill=X, expand=TRUE)

		f2 = Frame(self)
		def setAxis(number, *args):
			number = int(number)
			self.app.sendGCode("M10%02d" % number)

		for i in range(1, 13):
			self.app.bind("<<setAxis{}>>".format(i), functools.partial(setAxis, i))

		def makeButton(frame, number, icon, *args):
			b = Ribbon.LabelButton(frame, self, "<<setAxis{}>>".format(number),
					image=Utils.icons[icon],
					text=_(number),
					compound=TOP,
					width=40, height=40,
					background=Ribbon._BACKGROUND)
			tkExtra.Balloon.set(b, _(number))
			self.addWidget(b)
			return b #b.pack(side=TOP, fill=BOTH, expand=TRUE)

		f3 = Frame(f2)
		f4 = Frame(f3)
		makeButton(f4, "3", "flip_horizontal").grid(row=2, column=0)
		makeButton(f4, "2", "flip_angle").grid(row=1, column=1)
		makeButton(f4, "1", "flip_vertical").grid(row=0, column=2)
		makeButton(f4, "12", "flip_horizontal").grid(row=1, column=2)
		makeButton(f4, "8", "flip_-angle").grid(row=1, column=3)
		makeButton(f4, "7", "flip_horizontal").grid(row=2, column=4)
		makeButton(f4, "6", "flip_angle").grid(row=3, column=3)
		makeButton(f4, "5", "flip_vertical").grid(row=4, column=2)
		makeButton(f4, "4", "flip_-angle").grid(row=3, column=1)

		makeButton(f4, "10", "refresh").grid(row=2, column=2)

		f4.pack(side=LEFT,fill=BOTH, expand=FALSE)
		f4 = Frame(f3)
		makeButton(f4, "11", "pencil").grid(row=1, column=0)
		makeButton(f4, "9", "refresh").grid(row=1, column=1)

		Label(f4, textvariable=CNC.vars["currentJogAxisNumber"], font=DROFrame.dro_wpos).grid(row=2, column=0)
		f4.pack(side=LEFT,fill=BOTH, expand=TRUE)
		f3.pack(side=TOP, fill=BOTH, expand=TRUE)
		f2.pack(side=TOP, fill=BOTH, expand=TRUE)
		f.pack(side=TOP, fill=BOTH, expand=TRUE)

		# -- Separate zstep --
		self.zstep = self.step

		# Default steppings
		try:
			self.step1 = Utils.getFloat("Control","step1")
		except:
			self.step1 = 0.1

		try:
			self.step2 = Utils.getFloat("Control","step2")
		except:
			self.step2 = 1

		try:
			self.step3 = Utils.getFloat("Control","step3")
		except:
			self.step3 = 10

		#self.grid_columnconfigure(6,weight=1)
		try:
#			self.grid_anchor(CENTER)
			self.tk.call("grid","anchor",self,CENTER)
		except TclError:
			pass

	#----------------------------------------------------------------------
	def saveConfig(self):
		Utils.setFloat("Control", "step", self.step.get())
		if self.zstep is not self.step:
			Utils.setFloat("Control", "zstep", self.zstep.get())

	#----------------------------------------------------------------------
	# Jogging
	#----------------------------------------------------------------------
	def setJogSpeed(self,data=None):
		try:
			jogSpeed = float(self.jogSpeedEntry.get())
			CNC.vars["JogSpeed"] = jogSpeed
			self.app.focus_set()
		except ValueError:
			pass

	def getStep(self, axis='x'):
		isolatedStep = 'b' if self.isLathe else 'z'
		if axis == isolatedStep:
			zs = self.zstep.get()
			if zs == _NOZSTEP:
				return self.step.get()
			else:
				return zs
		else:
			return self.step.get()

	def move(self, axis:str, dirs:str, event=None):
		if event is not None and not self.acceptKey(): return
		cmd = ""
		for (a,d) in zip(axis,dirs):
			cmd += a+d+str(self.step.get())
		self.app.mcontrol.jog(cmd)

	def moveXup(self, event=None):
		if event is not None and not self.acceptKey(): return
		self.app.mcontrol.jog("X%s"%(self.step.get()))

	def moveXdown(self, event=None):
		if event is not None and not self.acceptKey(): return
		self.app.mcontrol.jog("X-%s"%(self.step.get()))

	def moveYup(self, event=None):
		if event is not None and not self.acceptKey(): return
		self.app.mcontrol.jog("Y%s"%(self.step.get()))

	def moveYdown(self, event=None):
		if event is not None and not self.acceptKey(): return
		self.app.mcontrol.jog("Y-%s"%(self.step.get()))

	def moveZup(self, event=None):
		if event is not None and not self.acceptKey(): return
		self.app.mcontrol.jog("Z%s"%(self.step.get()))

	def moveZdown(self, event=None):
		if event is not None and not self.acceptKey(): return
		self.app.mcontrol.jog("Z-%s"%(self.step.get()))

	def moveAup(self, event=None):
		if event is not None and not self.acceptKey(): return
		self.app.mcontrol.jog("A%s"%(self.step.get()))

	def moveAdown(self, event=None):
		if event is not None and not self.acceptKey(): return
		self.app.mcontrol.jog("A-%s"%(self.step.get()))

	def moveBup(self, event=None):
		if event is not None and not self.acceptKey(): return
		self.app.mcontrol.jog("B%s"%(self.step.get()))

	def moveBdown(self, event=None):
		if event is not None and not self.acceptKey(): return
		self.app.mcontrol.jog("B-%s"%(self.step.get()))

	def moveCup(self, event=None):
		if event is not None and not self.acceptKey(): return
		self.app.mcontrol.jog("C%s"%(self.step.get()))

	def moveCdown(self, event=None):
		if event is not None and not self.acceptKey(): return
		self.app.mcontrol.jog("C-%s"%(self.step.get()))

	def moveXdownYup(self, event=None):
		if event is not None and not self.acceptKey(): return
		self.app.mcontrol.jog("X-%sY%s"%(self.step.get(),self.step.get()))

	def moveXupYup(self, event=None):
		if event is not None and not self.acceptKey(): return
		self.app.mcontrol.jog("X%sY%s"%(self.step.get(),self.step.get()))

	def moveXdownYdown(self, event=None):
		if event is not None and not self.acceptKey(): return
		self.app.mcontrol.jog("X-%sY-%s"%(self.step.get(),self.step.get()))

	def moveXupYdown(self, event=None):
		if event is not None and not self.acceptKey(): return
		self.app.mcontrol.jog("X%sY-%s"%(self.step.get(),self.step.get()))

	def moveZdownXup(self, event=None):
		if event is not None and not self.acceptKey(): return
		self.app.mcontrol.jog("Z-%sX%s"%(self.step.get(),self.step.get()))

	def moveZupXup(self, event=None):
		if event is not None and not self.acceptKey(): return
		self.app.mcontrol.jog("Z%sX%s"%(self.step.get(),self.step.get()))

	def moveZdownXdown(self, event=None):
		if event is not None and not self.acceptKey(): return
		self.app.mcontrol.jog("Z-%sX-%s"%(self.step.get(),self.step.get()))

	def moveZupXdown(self, event=None):
		if event is not None and not self.acceptKey(): return
		self.app.mcontrol.jog("Z%sX-%s"%(self.step.get(),self.step.get()))


	def go2origin(self, event=None):
		self.sendGCode("G90")
		self.sendGCode("G0Z%d"%(CNC.vars['safe']))
		self.sendGCode("G0X0Y0")
		self.sendGCode("G0Z0")
		if self.isLathe:
			self.sendGCode("G0B0")

	#----------------------------------------------------------------------
	def setStep(self, s, zs=None):
		self.step.set("%.4g"%(s))
		if self.zstep is self.step or zs is None:
			self.event_generate("<<Status>>",
				data=_("Step: %g")%(s))
				#data=(_("Step: %g")%(s)))
		else:
			self.zstep.set("%.4g"%(zs))
			self.event_generate("<<Status>>",
				data=_("Step: %g    Zstep:%g ")%(s,zs))
				#data=(_("Step: %g    Zstep:%g ")%(s,zs)))

	#----------------------------------------------------------------------
	@staticmethod
	def _stepPower(step):
		try:
			step = float(step)
			if step <= 0.0: step = 1.0
		except:
			step = 1.0
		power = math.pow(10.0,math.floor(math.log10(step)))
		return round(step/power)*power, power

	#----------------------------------------------------------------------
	def incStep(self, event=None):
		if event is not None and not self.acceptKey(): return
		step, power = ControlFrame._stepPower(self.step.get())
		s = step+power
		if s<_LOWSTEP: s = _LOWSTEP
		elif s>_HIGHSTEP: s = _HIGHSTEP
		if self.zstep is not self.step and self.zstep.get() != _NOZSTEP:
			step, power = ControlFrame._stepPower(self.zstep.get())
			zs = step+power
			if zs<_LOWSTEP: zs = _LOWSTEP
			elif zs>_HIGHZSTEP: zs = _HIGHZSTEP
		else:
			zs=None
		self.setStep(s, zs)

	#----------------------------------------------------------------------
	def decStep(self, event=None):
		if event is not None and not self.acceptKey(): return
		step, power = ControlFrame._stepPower(self.step.get())
		s = step-power
		if s<=0.0: s = step-power/10.0
		if s<_LOWSTEP: s = _LOWSTEP
		elif s>_HIGHSTEP: s = _HIGHSTEP
		if self.zstep is not self.step and self.zstep.get() != _NOZSTEP:
			step, power = ControlFrame._stepPower(self.zstep.get())
			zs = step-power
			if zs<=0.0: zs = step-power/10.0
			if zs<_LOWSTEP: zs = _LOWSTEP
			elif zs>_HIGHZSTEP: zs = _HIGHZSTEP
		else:
			zs=None
		self.setStep(s, zs)

	#----------------------------------------------------------------------
	def mulStep(self, event=None):
		if event is not None and not self.acceptKey(): return
		step, power = ControlFrame._stepPower(self.step.get())
		s = step*10.0
		if s<_LOWSTEP: s = _LOWSTEP
		elif s>_HIGHSTEP: s = _HIGHSTEP
		if self.zstep is not self.step and self.zstep.get() != _NOZSTEP:
			step, power = ControlFrame._stepPower(self.zstep.get())
			zs = step*10.0
			if zs<_LOWSTEP: zs = _LOWSTEP
			elif zs>_HIGHZSTEP: zs = _HIGHZSTEP
		else:
			zs=None
		self.setStep(s, zs)

	#----------------------------------------------------------------------
	def divStep(self, event=None):
		if event is not None and not self.acceptKey(): return
		step, power = ControlFrame._stepPower(self.step.get())
		s = step/10.0
		if s<_LOWSTEP: s = _LOWSTEP
		elif s>_HIGHSTEP: s = _HIGHSTEP
		if self.zstep is not self.step and self.zstep.get() != _NOZSTEP:
			step, power = ControlFrame._stepPower(self.zstep.get())
			zs = step/10.0
			if zs<_LOWSTEP: zs = _LOWSTEP
			elif zs>_HIGHZSTEP: zs = _HIGHZSTEP
		else:
			zs=None
		self.setStep(s, zs)

	#----------------------------------------------------------------------
	def setStep1(self, event=None):
		if event is not None and not self.acceptKey(): return
		self.setStep(self.step1, self.step1)

	#----------------------------------------------------------------------
	def setStep2(self, event=None):
		if event is not None and not self.acceptKey(): return
		self.setStep(self.step2, self.step2)

	#----------------------------------------------------------------------
	def setStep3(self, event=None):
		if event is not None and not self.acceptKey(): return
		self.setStep(self.step3, self.step2)
		
#===============================================================================
# abc ControlFrame
#===============================================================================
class abcControlFrame(CNCRibbon.PageExLabelFrame):
	def __init__(self, master, app):
		CNCRibbon.PageExLabelFrame.__init__(self, master, "abcControl", _("abcControl"), app)

		frame = Frame(self())
		frame.pack(side=TOP, fill=X)

		row,col = 0,0
		Label(frame, text=_("A")).grid(row=row, column=col)

		col += 3
		Label(frame, text=_("C")).grid(row=row, column=col)

		# ---
		row += 1
		col = 0

		width=3
		height=2

		b = Button(frame, text=Unicode.BLACK_UP_POINTING_TRIANGLE,
					command=self.moveAup,
					width=width, height=height,
					activebackground="LightYellow")
		b.grid(row=row, column=col, sticky=EW)
		tkExtra.Balloon.set(b, _("Move +A"))
		self.addWidget(b)

		col += 2
		b = Button(frame, text=Unicode.UPPER_LEFT_TRIANGLE,
					command=self.moveBdownCup,
					width=width, height=height,
					activebackground="LightYellow")

		b.grid(row=row, column=col, sticky=EW)
		tkExtra.Balloon.set(b, _("Move -B +C"))
		self.addWidget(b)

		col += 1
		b = Button(frame, text=Unicode.BLACK_UP_POINTING_TRIANGLE,
					command=self.moveCup,
					width=width, height=height,
					activebackground="LightYellow")
		b.grid(row=row, column=col, sticky=EW)
		tkExtra.Balloon.set(b, _("Move +C"))
		self.addWidget(b)

		col += 1
		b = Button(frame, text=Unicode.UPPER_RIGHT_TRIANGLE,
					command=self.moveBupCup,
					width=width, height=height,
					activebackground="LightYellow")
		b.grid(row=row, column=col, sticky=EW)
		tkExtra.Balloon.set(b, _("Move +B +C"))
		self.addWidget(b)

		col += 2
		b = Button(frame, text=u"\u00D710",
				command=self.mulStep,
				width=3,
				padx=1, pady=1)
		b.grid(row=row, column=col, sticky=EW+S)
		tkExtra.Balloon.set(b, _("Multiply step by 10"))
		self.addWidget(b)

		col += 1
		b = Button(frame, text=_("+"),
				command=self.incStep,
				width=3,
				padx=1, pady=1)
		b.grid(row=row, column=col, sticky=EW+S)
		tkExtra.Balloon.set(b, _("Increase step by 1 unit"))
		self.addWidget(b)

		# ---
		row += 1

		col = 1
		Label(frame, text=_("B"), width=3, anchor=E).grid(row=row, column=col, sticky=E)

		col += 1
		b = Button(frame, text=Unicode.BLACK_LEFT_POINTING_TRIANGLE,
					command=self.moveBdown,
					width=width, height=height,
					activebackground="LightYellow")
		b.grid(row=row, column=col, sticky=EW)
		tkExtra.Balloon.set(b, _("Move -B"))
		self.addWidget(b)

		col += 1
		b = Button(frame, text=Unicode.LARGE_CIRCLE,
					command=self.go2abcorigin,
					width=width, height=height,
					activebackground="LightYellow")
		b.grid(row=row, column=col, sticky=EW)
		tkExtra.Balloon.set(b, _("Return ABC to 0."))
		self.addWidget(b)

		col += 1
		b = Button(frame, text=Unicode.BLACK_RIGHT_POINTING_TRIANGLE,
					command=self.moveBup,
					width=width, height=height,
					activebackground="LightYellow")
		b.grid(row=row, column=col, sticky=EW)
		tkExtra.Balloon.set(b, _("Move +B"))
		self.addWidget(b)

		# --
		col += 1
		Label(frame,"",width=2).grid(row=row,column=col)
		
		col += 1
		self.step = tkExtra.Combobox(frame, width=6, background=tkExtra.GLOBAL_CONTROL_BACKGROUND)
		self.step.grid(row=row, column=col, columnspan=2, sticky=EW)
		self.step.set(Utils.config.get("abcControl","step"))
		self.step.fill(map(float, Utils.config.get("abcControl","abcsteplist").split()))
		tkExtra.Balloon.set(self.step, _("Step for every move operation"))
		self.addWidget(self.step)

		# -- Separate astep --
		try:
			astep = Utils.config.get("abcControl","astep")
			self.astep = tkExtra.Combobox(frame, width=4, background=tkExtra.GLOBAL_CONTROL_BACKGROUND)
			self.astep.grid(row=row, column=0, columnspan=1, sticky=EW)
			self.astep.set(astep)
			asl = [_NOASTEP]
			asl.extend(map(float, Utils.config.get("abcControl","asteplist").split()))
			self.astep.fill(asl)
			tkExtra.Balloon.set(self.astep, _("Step for A move operation"))
			self.addWidget(self.astep)
		except:
			self.astep = self.step

		# Default steppings
		try:
			self.step1 = Utils.getFloat("abcControl","step1")
		except:
			self.step1 = 0.1

		try:
			self.step2 = Utils.getFloat("abcControl","step2")
		except:
			self.step2 = 1

		try:
			self.step3 = Utils.getFloat("abcControl","step3")
		except:
			self.step3 = 10

		# ---
		row += 1
		col = 0

		b = Button(frame, text=Unicode.BLACK_DOWN_POINTING_TRIANGLE,
					command=self.moveAdown,
					width=width, height=height,
					activebackground="LightYellow")
		b.grid(row=row, column=col, sticky=EW)
		tkExtra.Balloon.set(b, _("Move -A"))
		self.addWidget(b)

		col += 2
		b = Button(frame, text=Unicode.LOWER_LEFT_TRIANGLE,
					command=self.moveBdownCdown,
					width=width, height=height,
					activebackground="LightYellow")
		b.grid(row=row, column=col, sticky=EW)
		tkExtra.Balloon.set(b, _("Move -B -C"))
		self.addWidget(b)

		col += 1
		b = Button(frame, text=Unicode.BLACK_DOWN_POINTING_TRIANGLE,
					command=self.moveCdown,
					width=width, height=height,
					activebackground="LightYellow")
		b.grid(row=row, column=col, sticky=EW)
		tkExtra.Balloon.set(b, _("Move -C"))
		self.addWidget(b)

		col += 1
		b = Button(frame, text=Unicode.LOWER_RIGHT_TRIANGLE,
					command=self.moveBupCdown,
					width=width, height=height,
					activebackground="LightYellow")
		b.grid(row=row, column=col, sticky=EW)
		tkExtra.Balloon.set(b, _("Move +B -C"))
		self.addWidget(b)

		col += 2
		b = Button(frame, text=u"\u00F710",
					command=self.divStep,
					padx=1, pady=1)
		b.grid(row=row, column=col, sticky=EW+N)
		tkExtra.Balloon.set(b, _("Divide step by 10"))
		self.addWidget(b)

		col += 1
		b = Button(frame, text=_("-"),
					command=self.decStep,
					padx=1, pady=1)
		b.grid(row=row, column=col, sticky=EW+N)
		tkExtra.Balloon.set(b, _("Decrease step by 1 unit"))
		self.addWidget(b)

		#self.grid_columnconfigure(6,weight=1)
		try:
#			self.grid_anchor(CENTER)
			self.tk.call("grid","anchor",self,CENTER)
		except TclError:
			pass

	#----------------------------------------------------------------------
	def saveConfig(self):
		Utils.setFloat("abcControl", "step", self.step.get())
		if self.astep is not self.step:
			Utils.setFloat("abcControl", "astep", self.astep.get())

	#----------------------------------------------------------------------
	# Jogging
	#----------------------------------------------------------------------
	def getStep(self, axis='a'):
		if axis == 'a':
			aas = self.astep.get()
			if aas == _NOASTEP:
				return self.step.get()
			else:
				return aas
		else:
			return self.step.get()

	def moveBup(self, event=None):
		if event is not None and not self.acceptKey(): return
		self.app.mcontrol.jog("B%s"%(self.step.get()))

	def moveBdown(self, event=None):
		if event is not None and not self.acceptKey(): return
		self.app.mcontrol.jog("B-%s"%(self.step.get()))

	def moveCup(self, event=None):
		if event is not None and not self.acceptKey(): return
		self.app.mcontrol.jog("C%s"%(self.step.get()))

	def moveCdown(self, event=None):
		if event is not None and not self.acceptKey(): return
		self.app.mcontrol.jog("C-%s"%(self.step.get()))

	def moveBdownCup(self, event=None):
		if event is not None and not self.acceptKey(): return
		self.app.mcontrol.jog("B-%C%s"%(self.step.get(),self.step.get()))

	def moveBupCup(self, event=None):
		if event is not None and not self.acceptKey(): return
		self.app.mcontrol.jog("B%sC%s"%(self.step.get(),self.step.get()))

	def moveBdownCdown(self, event=None):
		if event is not None and not self.acceptKey(): return
		self.app.mcontrol.jog("B-%sC-%s"%(self.step.get(),self.step.get()))

	def moveBupCdown(self, event=None):
		if event is not None and not self.acceptKey(): return
		self.app.mcontrol.jog("B%sC-%s"%(self.step.get(),self.step.get()))

	def moveAup(self, event=None):
		if event is not None and not self.acceptKey(): return
		self.app.mcontrol.jog("A%s"%(self.getStep('z')))

	def moveAdown(self, event=None):
		if event is not None and not self.acceptKey(): return
		self.app.mcontrol.jog("A-%s"%(self.getStep('z')))

	def go2abcorigin(self, event=None):
		self.sendGCode("G90")
		#self.sendGCode("G0A%d"%(CNC.vars['safe']))
		self.sendGCode("G0B0C0")
		self.sendGCode("G0A0")

	#----------------------------------------------------------------------
	def setStep(self, s, aas=None):
		self.step.set("%.4g"%(s))
		if self.astep is self.step or aas is None:
			self.event_generate("<<Status>>",
				data=_("Step: %g")%(s))
				#data=(_("Step: %g")%(s)))
		else:
			self.astep.set("%.4g"%(aas))
			self.event_generate("<<Status>>",
				data=_("Step: %g    Astep:%g ")%(s,aas))
				#data=(_("Step: %g    Zstep:%g ")%(s,zs)))

	#----------------------------------------------------------------------
	@staticmethod
	def _stepPower(step):
		try:
			step = float(step)
			if step <= 0.0: step = 1.0
		except:
			step = 1.0
		power = math.pow(10.0,math.floor(math.log10(step)))
		return round(step/power)*power, power

	#----------------------------------------------------------------------
	def incStep(self, event=None):
		if event is not None and not self.acceptKey(): return
		step, power = abcControlFrame._stepPower(self.step.get())
		s = step+power
		if s<_LOWSTEP: s = _LOWSTEP
		elif s>_HIGHSTEP: s = _HIGHSTEP
		if self.astep is not self.step and self.astep.get() != _NOASTEP:
			step, power = abcControlFrame._stepPower(self.astep.get())
			aas = step+power
			if aas<_LOWSTEP: aas = _LOWSTEP
			elif aas>_HIGHASTEP: aas = _HIGHASTEP
		else:
			aas=None
		self.setStep(s, aas)

	#----------------------------------------------------------------------
	def decStep(self, event=None):
		if event is not None and not self.acceptKey(): return
		step, power = abcControlFrame._stepPower(self.step.get())
		s = step-power
		if s<=0.0: s = step-power/10.0
		if s<_LOWSTEP: s = _LOWSTEP
		elif s>_HIGHSTEP: s = _HIGHSTEP
		if self.astep is not self.step and self.astep.get() != _NOASTEP:
			step, power = abcControlFrame._stepPower(self.astep.get())
			aas = step-power
			if aas<=0.0: aas = step-power/10.0
			if aas<_LOWSTEP: aas = _LOWSTEP
			elif aas>_HIGHASTEP: aas = _HIGHASTEP
		else:
			aas=None
		self.setStep(s, aas)

	#----------------------------------------------------------------------
	def mulStep(self, event=None):
		if event is not None and not self.acceptKey(): return
		step, power = abcControlFrame._stepPower(self.step.get())
		s = step*10.0
		if s<_LOWSTEP: s = _LOWSTEP
		elif s>_HIGHSTEP: s = _HIGHSTEP
		if self.astep is not self.step and self.astep.get() != _NOASTEP:
			step, power = abcControlFrame._stepPower(self.astep.get())
			aas = step*10.0
			if aas<_LOWSTEP: aas = _LOWSTEP
			elif aas>_HIGHASTEP: aas = _HIGHASTEP
		else:
			aas=None
		self.setStep(s, aas)

	#----------------------------------------------------------------------
	def divStep(self, event=None):
		if event is not None and not self.acceptKey(): return
		step, power = abcControlFrame._stepPower(self.step.get())
		s = step/10.0
		if s<_LOWSTEP: s = _LOWSTEP
		elif s>_HIGHSTEP: s = _HIGHSTEP
		if self.astep is not self.step and self.astep.get() != _NOASTEP:
			step, power = abcControlFrame._stepPower(self.astep.get())
			aas = step/10.0
			if aas<_LOWSTEP: aas = _LOWSTEP
			elif aas>_HIGHASTEP: aas = _HIGHASTEP
		else:
			aas=None
		self.setStep(s, aas)

	#----------------------------------------------------------------------
	def setStep1(self, event=None):
		if event is not None and not self.acceptKey(): return
		self.setStep(self.step1, self.step1)

	#----------------------------------------------------------------------
	def setStep2(self, event=None):
		if event is not None and not self.acceptKey(): return
		self.setStep(self.step2, self.step2)

	#----------------------------------------------------------------------
	def setStep3(self, event=None):
		if event is not None and not self.acceptKey(): return
		self.setStep(self.step3, self.step2)


class NotebookFrame(CNCRibbon.PageLabelFrame):
    def __init__(self, master, app):
        CNCRibbon.PageLabelFrame.__init__(self, master, "Notebook", _("Notebook"), app)

        # --- Canvas ---
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(side=TOP, expand=YES, fill=BOTH)

        self.gcodeViewFrame = GCodeViewer.GCodeViewer(self.notebook, app)

        self.gcodeViewFrame.pack(side=TOP, fill=BOTH, expand=YES)
        self.canvasFrame = CNCCanvas.CanvasFrame(self.notebook, app)
        self.canvasFrame.pack(side=TOP, fill=BOTH, expand=YES)

        if Utils.getBool("CNC", "pidLog", False):
                self.pidLogFrame = PidLog.PidLogFrame(self.notebook, app)
                self.pidLogFrame.pack(side=TOP, fill=BOTH, expand=YES)

        self.notebook.add(self.gcodeViewFrame.lb, text="GCode")
        self.notebook.add(self.canvasFrame, text="Graph")

        if Utils.getBool("CNC", "pidLog", False):
                self.notebook.add(self.pidLogFrame, text="PidLog")


#===============================================================================
# ProgramCreateFrame
#===============================================================================
class ProgramCreateFrame(CNCRibbon.PageLabelFrame):
	def __init__(self, master, app):
		self._gUpdate = False
		self.app = app
		CNCRibbon.PageLabelFrame.__init__(self, master, "ProgramCreate", _("ProgramCreate"), app)
		f = Frame(self, highlightbackground="black", highlightthickness=2)
		Label(f, text="Movimentacao").pack(side=TOP, fill=BOTH)
		b = Button(f, text="Movimento rapido para posicao atual",
					command=self.goToPosition,
					activebackground="LightYellow")
		b.pack(side=TOP, fill=BOTH)
		self.addWidget(b)
		f2 = Frame(f)
		b = Button(f2, text="Movimento controlado para posicao atual",
					command=self.traverseToPosition,
					activebackground="LightYellow")
		b.pack(side=LEFT,fill=BOTH, expand=TRUE)
		self.addWidget(b)
		self.feed = tkExtra.FloatEntry(f2, background=tkExtra.GLOBAL_CONTROL_BACKGROUND, disabledforeground="Black",width=5, font=DROFrame.dro_mpos)
		self.feed.pack(side=LEFT, fill=BOTH, expand=TRUE)
		self.feed.bind('<Return>',lambda ev=None, s=self: s.app.focus_set())
		self.feed.bind('<KP_Enter>',lambda ev=None, s=self: s.app.focus_set())
		f2.pack(side=TOP, fill=NONE, expand=False)
		f.pack(side=LEFT, fill=Y, expand=False)
		ttk.Separator(self, orient=VERTICAL).pack(side=LEFT, padx=5)
		f = Frame(self, highlightbackground="black", highlightthickness=2)
		Label(f, text="Programa").pack(side=TOP, fill=BOTH)
		f2 = Frame(f)
		b = Button(f2, text="Salvar Programa",
					command=self.saveProgram,
					activebackground="LightYellow")
		b.pack(side=TOP, fill=BOTH, expand=FALSE)
		self.addWidget(b)
		b = Button(f2, text="Novo Programa",
			 command=self.clean, activebackground="LightYellow")
		b.pack(side=TOP, fill=BOTH, expand=FALSE)
		b = Button(f2, text="Recarrega Programa",
			 command=self.reloadProgram, activebackground="LightYellow")
		b.pack(side=TOP, fill=BOTH, expand=FALSE)
		f2.pack(side=TOP, fill=Y, expand=False)
		f.pack(side=LEFT, fill=Y, expand=False)

	def reloadProgram(self):
		Page.lframes["Notebook"].gcodeViewFrame.reload()
		Page.lframes["Notebook"].gcodeViewFrame.seeLastElement()

	def clean(self):
		self.app.newFile()
		self.app.gcode._addLine("M47 P1")
		Page.lframes["Notebook"].gcodeViewFrame.reload()

	def saveProgram(self, *args):
		self.app.saveAll()
		self.app.reload()

	def getFeed(self):
		try:
			return float(self.feed.get())
		except:
			return 1000

	def getPort(self, numb):
		return 1 if numb>6 else 0
	def getPortState(self, numb):
		numb -= 1 # numb e [1,12] => numb e [0,12]
		numb //= 3 # 123 -> 0, 456->1, 789->2, 101112->3
		return numb%2

	def prepareMove(self):
		number = CNC.vars["currentJogAxisNumber"].get()
		self.app.gcode._addLine("M10%02d (Seleciona motor %d)" % (number, number))
		axis = self.app.getJogAxis()
		position = CNC.vars["w{}".format(axis.lower())]
		return axis, position

	def goToPosition(self):
		axis, position = self.prepareMove()
		cmd = "G0 {} {} (Movimento rapido com motor {})".format(axis, position, CNC.vars["currentJogAxisNumber"].get())
		self.app.gcode._addLine(cmd)
		Page.lframes["Notebook"].gcodeViewFrame.reload()
		Page.lframes["Notebook"].gcodeViewFrame.seeLastElement()

	def traverseToPosition(self):
		axis, position = self.prepareMove()
		cmd = "G1 {} {} F{} (Movimento controlado com motor {})".format(axis, position, self.getFeed(), CNC.vars["currentJogAxisNumber"].get())
		self.app.gcode._addLine(cmd)
		Page.lframes["Notebook"].gcodeViewFrame.reload()
		Page.lframes["Notebook"].gcodeViewFrame.seeLastElement()

#===============================================================================
# SpindleFrame
#===============================================================================
class SpindleFrame(CNCRibbon.PageLabelFrame):
	def __init__(self, master, app):
		self._gUpdate = False
		CNCRibbon.PageLabelFrame.__init__(self, master, "Spindle", _("Spindle"), app)
		self.spindle = BooleanVar()
		self.spindleSpeed = IntVar()
		f = Frame(self)
		f2 = Frame(f)
		f3 = Frame(f2)
		b = Checkbutton(f3, text=_("Spindle"),
				image=Utils.icons["spinningtop"],
				command=self.spindleControl,
				compound=LEFT,
				indicatoron=False,
				variable=self.spindle,
				padx=1,
				pady=0)
		tkExtra.Balloon.set(b, _("Start/Stop spindle (M3/M5)"))
		b.pack(side=LEFT, fill=BOTH)
		self.addWidget(b)
		b = Scale(f3,	variable=self.spindleSpeed,
				command=self.spindleControl,
				showvalue=True,
				orient=HORIZONTAL,
				from_=Utils.config.get("CNC","spindlemin"),
				to_=Utils.config.get("CNC","spindlemax"))
		tkExtra.Balloon.set(b, _("Set spindle RPM"))
		b.pack(side=LEFT, fill=X, expand=TRUE)
		self.addWidget(b)
		f3.pack(side=TOP, fill=BOTH, expand=TRUE)
		f2.pack(side=TOP, fill=BOTH, expand=TRUE)
		f.pack(side=TOP, fill=BOTH, expand=TRUE)

	def updateG(self):
		self._gUpdate = True
		try:
			focus = self.focus_get()
		except:
			focus = None
		try:
			self.spindle.set(CNC.vars["spindle"]=="M3")
			self.spindleSpeed.set(int(CNC.vars["rpm"]))
		except KeyError as e:
			print(e)
		self._gUpdate = False
	#----------------------------------------------------------------------
	def spindleControl(self, event=None):
		if self._gUpdate: return
		# Avoid sending commands before unlocking
		if CNC.vars["state"] in (Sender.CONNECTED, Sender.NOT_CONNECTED): return
		if self.spindle.get():
			self.sendGCode("M3 S%d"%(self.spindleSpeed.get()))
		else:
			self.sendGCode("M5")

#===============================================================================
# StateFrame
#===============================================================================
class StateFrame(CNCRibbon.PageLabelFrame):
	def __init__(self, master, app):
		global wcsvar
		CNCRibbon.PageLabelFrame.__init__(self, master, "State", _("State"), app)
		self._gUpdate = False

		# State
		f = Frame(self)
		# ===
		f2 = Frame(f)
		for p,w in enumerate(WCS):
			b = Radiobutton(f2, text=w,
					foreground="DarkRed",
					font = "Helvetica,14",
					padx=1, pady=1,
					variable=wcsvar,
					value=p,
					indicatoron=FALSE,
					activebackground="LightYellow",
					command=self.wcsChange)
			b.pack(side=LEFT, fill=X, expand=YES)
			tkExtra.Balloon.set(b, _("Switch to workspace %s")%(w))
			self.addWidget(b)
		f2.pack(side=TOP, fill=X, expand=TRUE)
		f2 = Frame(f)
		lef = Frame(f2) # side = left
		rig = Frame(f2) # side = Right
		# populate gstate dictionary
		self.gstate = {}	# $G state results widget dictionary
	
		# Tool
		f3 = Frame(lef)
		Label(f3, text=_("Tool:"), width=15).pack(side=LEFT)
		self.tool = Label(f3, 
				background=tkExtra.GLOBAL_CONTROL_BACKGROUND, 
				width=7, relief=RAISED)
		self.tool.pack(side=LEFT)
		tkExtra.Balloon.set(self.tool, _("Tool number [T#]"))
		f3.pack(side=TOP, fill=X, expand=TRUE)


		# Feed speed
		f3 = Frame(rig)
		Label(f3, text=_("Feed:"), width=15).pack(side=LEFT)
		self.feedRate = Label(f3, 
				background=tkExtra.GLOBAL_CONTROL_BACKGROUND, 
				disabledforeground="Black", width=7,
				relief=RAISED)
		self.feedRate.pack(side=LEFT)
		tkExtra.Balloon.set(self.feedRate, _("Feed Rate [F#]"))
		f3.pack(side=TOP, fill=X, expand=TRUE)

		# TLO
		f3 = Frame(lef)
		Label(f3, text=_("TLO:"), width=15).pack(side=LEFT)
		self.tlo = Label(f3, background=tkExtra.GLOBAL_CONTROL_BACKGROUND, disabledforeground="Black", 
				width=7, relief=RAISED)
		self.tlo.pack(side=LEFT)
		tkExtra.Balloon.set(self.tlo, _("Tool length offset [G43.1#]"))
		self.addWidget(self.tlo)
		f3.pack(side=TOP, fill=X, expand=TRUE)

		f3 = Frame(lef)
		Label(f3, text=_("RealRpm:"), width=15).pack(side=LEFT)
		self.realRpm = Label(f3, background=tkExtra.GLOBAL_CONTROL_BACKGROUND, disabledforeground="Black", 
				width=7, relief=RAISED)
		self.realRpm.pack(side=LEFT)
		f3.pack(side=TOP, fill=X, expand=TRUE)

		# Plane
		f3 = Frame(rig)
		Label(f3, text=_("Spindle:"), width=15).pack(side=LEFT)
		spinToggle = Button(f3, text=_("Spindle"),
				command=self.spindleToggle,
				padx=1,
				pady=0)
		tkExtra.Balloon.set(spinToggle, _("Toogle spindle"))
		spinToggle.pack(side=LEFT)
		f3.pack(side=TOP,fill=X, expand=TRUE)

		# Coolant control

		self.coolant = BooleanVar()
		self.mist = BooleanVar()
		self.flood = BooleanVar()

		f3 = Frame(rig)
		Label(f3, text=_("Coolant:"),width=15).pack(side=LEFT)

		floodToogle = Button(f3, text=_("Flood"),
				command=self.coolantFlood,
				padx=1,
				pady=0)
		tkExtra.Balloon.set(floodToogle, _("Start flood (M8)"))
		floodToogle.pack(side=LEFT)
		mistToogle = Button(f3, text=_("Mist"),
				command=self.coolantMist,
				padx=1,
				pady=0)
		tkExtra.Balloon.set(mistToogle, _("Start mist (M7)"))
		mistToogle.pack(side=LEFT)

		f3.pack(side=TOP,fill=X, expand=TRUE)

		lef.pack(side=LEFT, fill=BOTH, expand=TRUE)
		rig.pack(side=LEFT, fill=BOTH, expand=TRUE)

		f2.pack(side=TOP, fill=BOTH, expand=TRUE)
		# Spindle
		f2 = Frame(f)

		self.feedOverride = IntVar()
		self.feedOverride.set(100)
		self.rapidOverride = IntVar()
		self.rapidOverride.set(100)
		self.spindleOverride = IntVar()
		self.spindleOverride.set(100)

		def makeScale(frame, name:str, override, from_, to_, res):
			f = Frame(frame)
			f2 = Frame(f)
			Label(f2, text=name+" % ", font=DROFrame.dro_mpos).pack(side=LEFT)
			b = Button(f2, text=_("Reset"), pady=0, 
					command=functools.partial(self.resetOverride, override,name))
			b.pack(side=LEFT)
			tkExtra.Balloon.set(b, _("Reset override to 100%"))
			f2.pack(side=TOP,fill=BOTH, expand=TRUE)

			scale = Scale(f,
					command=functools.partial(self.overrideChange, override,name),
					variable=override,
					showvalue=True,
					orient=HORIZONTAL,
					from_=from_,
					to_=to_,
					resolution=res)
			scale.pack(side=TOP, fill=BOTH, expand=TRUE)
			f.pack(side=TOP, fill=BOTH, expand=TRUE)
			return scale

		def makeScaleInline(frame, name, override, from_, to_, res):
			f = Frame(frame)
			f2 = Frame(f)
			Label(f2, text=name+" % ", font=DROFrame.dro_mpos).pack(side=LEFT)
			b = Button(f2, text=_("Reset"), pady=0, 
					command=functools.partial(self.resetOverride, override,name))
			b.pack(side=LEFT)
			tkExtra.Balloon.set(b, _("Reset override to 100%"))
			f2.pack(side=LEFT,fill=BOTH, expand=TRUE)

			scale = Scale(f,
					command=functools.partial(self.overrideChange, override,name),
					variable=override,
					showvalue=True,
					orient=HORIZONTAL,
					from_=from_,
					to_=to_,
					resolution=res)
			scale.pack(side=LEFT, fill=BOTH, expand=TRUE)
			f.pack(side=TOP, fill=BOTH, expand=TRUE)
			return scale

		ttk.Separator(f2, orient=HORIZONTAL).pack(side=TOP, fill=BOTH, expand=TRUE, pady=5)
		f3 = Frame(f2)
		f4 = Frame(f3)
		self.feedScale = makeScale(f4, "Feed", self.feedOverride, 1, 200, 1)
		f4.pack(side=LEFT, fill=BOTH, expand=TRUE)
		ttk.Separator(f3, orient=VERTICAL).pack(side=LEFT, fill=BOTH, padx=5)
		f4 = Frame(f3)
		self.rapidScale = makeScale(f4, "Rapid", self.rapidOverride, 1, 100, 1)
		f4.pack(side=LEFT, fill=BOTH, expand=TRUE)
		f3.pack(side=TOP, fill=X, expand=TRUE)
		ttk.Separator(f2, orient=HORIZONTAL).pack(side=TOP, fill=BOTH, expand=TRUE, pady=5)
		f3 = Frame(f2)
		self.spindleScale = makeScaleInline(f3, "Spindle", self.spindleOverride, 1, 200, 1)
		f3.pack(side=TOP, fill=X, expand=TRUE)
		ttk.Separator(f2, orient=HORIZONTAL).pack(side=TOP, fill=BOTH, expand=TRUE, pady=5)
		f2.pack(side=TOP, fill=BOTH, expand=TRUE)

		f.pack(side=TOP, fill=BOTH, expand=TRUE)

	def setOverride(self, name, value):
		name = name.lower()
		override = self.feedOverride
		if name == "feed": override = self.feedOverride
		elif name == "rapid": override = self.rapidOverride
		elif name == "spindle": override = self.spindleOverride

		override.set(value)
		self.overrideChange(override, name)

	#----------------------------------------------------------------------
	def overrideChange(self, override, name, event=None):
		CNC.vars["_Ov"+name.capitalize()] = override.get()
		CNC.vars["_OvChanged"] = True

	#----------------------------------------------------------------------
	def resetOverride(self, override, name, event=None):
		override.set(100)
		self.overrideChange(override, name)

	#----------------------------------------------------------------------
	def overridePlus(self, event=None):
		feedValue = self.feedOverride.get() + 5
		feedValue = min(feedValue, 200)
		self.setOverride("feed", feedValue)
		self.setOverride("rapid", min(feedValue, 100))

	def overrideMinus(self, event=None):
		feedValue = self.feedOverride.get() - 5
		feedValue = max(feedValue, 1)
		self.setOverride("feed", feedValue)
		self.setOverride("rapid", min(feedValue, 100))

	#----------------------------------------------------------------------
	def _gChange(self, value, dictionary):
		for k,v in dictionary.items():
			if v==value:
				self.sendGCode(k)
				return

	#----------------------------------------------------------------------
	def distanceChange(self):
		if self._gUpdate: return

	#----------------------------------------------------------------------
	def unitsChange(self):
		if self._gUpdate: return

	#----------------------------------------------------------------------
	def planeChange(self):
		if self._gUpdate: return
		self._gChange(self.plane.get(), PLANE)

	#----------------------------------------------------------------------
	def setFeedRate(self, event=None):
		if self._gUpdate: return
		try:
			feed = float(self.feedRate['text'])
			self.sendGCode("F%g"%(feed))
			self.event_generate("<<CanvasFocus>>")
		except ValueError:
			pass

	#----------------------------------------------------------------------
	def setTLO(self, event=None):
		#if self._probeUpdate: return
		try:
			tlo = float(self.tlo['text'])
			#print("G43.1Z%g"%(tlo))
			#self.sendGCode("G43.1Z%g"%(tlo))
			self.app.mcontrol.viewParameters()
			self.event_generate("<<CanvasFocus>>")
		except ValueError:
			pass

	#----------------------------------------------------------------------
	def setTool(self, event=None):
		pass

	#----------------------------------------------------------------------
	def coolantMist(self, event=None):
		if self._gUpdate: return
		# Avoid sending commands before unlocking
		if CNC.vars["state"] in (Sender.CONNECTED, Sender.NOT_CONNECTED):
			return
		self.app.sendHex("0xA1")

	#----------------------------------------------------------------------
	def coolantFlood(self, event=None):
		if self._gUpdate: return
		# Avoid sending commands before unlocking
		if CNC.vars["state"] in (Sender.CONNECTED, Sender.NOT_CONNECTED):
			return
		self.app.sendHex("0xA0")

	#----------------------------------------------------------------------
	def spindleToggle(self, event=None):
		if self._gUpdate: return
		# Avoid sending commands before unlocking
		if CNC.vars["state"] in (Sender.CONNECTED, Sender.NOT_CONNECTED):
			return
		self.app.sendHex("0x9E")

	#----------------------------------------------------------------------
	def coolantOff(self, event=None):
		if self._gUpdate: return
		# Avoid sending commands before unlocking
		if CNC.vars["state"] in (Sender.CONNECTED, Sender.NOT_CONNECTED):
			return
		self.sendGCode("M9")

	def updateRpm(self):
		self.realRpm['text'] = str(CNC.vars["realRpm"])

	#----------------------------------------------------------------------
	def updateG(self):
		global wcsvar
		self._gUpdate = True
		try:
			focus = self.focus_get()
		except:
			focus = None

		try:
			wcsvar.set(WCS.index(CNC.vars["WCS"]))
			self.feedRate['text'] = str(CNC.vars["feed"])
			self.tool['text'] = str(CNC.vars["tool"])
			self.tlo['text'] = str(CNC.vars["TLO"])
			self.realRpm['text'] = str(CNC.vars["realRpm"])
		except KeyError as e:
			print(e)
			pass

		self._gUpdate = False

	#----------------------------------------------------------------------
	def updateFeed(self):
		self.feedRate['text'] = CNC.vars["curfeed"]

	#----------------------------------------------------------------------
	def wcsChange(self):
		global wcsvar
		self.sendGCode(WCS[wcsvar.get()])
		self.app.mcontrol.viewState()


#===============================================================================
# Execution Page
#===============================================================================
class ExecutionPage(CNCRibbon.Page):
	__doc__ = _("CNC communication and control")
	_name_  = N_("Execution")
	_icon_  = "control"

	#----------------------------------------------------------------------
	# Add a widget in the widgets list to enable disable during the run
	#----------------------------------------------------------------------
	def register(self):
		global wcsvar
		wcsvar = IntVar()
		wcsvar.set(0)

		self._register((ConnectionGroup, UserGroup, RunGroup),
			(DROFrame, abcDROFrame, NotebookFrame, StateFrame))
	def activate(self, **kwargs):
		CNC.vars["execution"] = True
		return super().activate()

	def release(self, **kwargs):
		CNC.vars["execution"] = False
		return super().release()



#===============================================================================
# Jog Page
#===============================================================================
class JogPage(CNCRibbon.Page):
	__doc__ = _("CNC communication and control")
	_name_  = N_("Jog")
	_icon_  = "control"

	#----------------------------------------------------------------------
	# Add a widget in the widgets list to enable disable during the run
	#----------------------------------------------------------------------
	def register(self):
		global wcsvar
		wcsvar = IntVar()
		wcsvar.set(0)

		self._register((ConnectionGroup, UserGroup, RunGroup, ZeroGroup, ToolGroup),
			(DROFrame, abcDROFrame, NotebookFrame, ControlFrame, abcControlFrame, StateFrame, SpindleFrame, MdiFrame, ProgramCreateFrame))
	def activate(self, **kwargs):
		CNC.vars["JogActive"] = True

	def release(self, **kwargs):
		CNC.vars["JogActive"] = False

