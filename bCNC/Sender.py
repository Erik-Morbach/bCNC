# -*- coding: utf-8 -*-
# $Id: bCNC.py,v 1.6 2014/10/15 15:04:48 bnv Exp bnv $
#
# Author: Vasilis Vlachoudis
#  Email: vvlachoudis@gmail.com
#   Date: 17-Jun-2015

from __future__ import absolute_import
from __future__ import print_function

__author__  = "Vasilis Vlachoudis"
__email__   = "vvlachoudis@gmail.com"

import os
import re
import sys
import glob
import traceback
import rexx
import time
import threading
import webbrowser
import struct
import MacroEngine
import Command
import ProcessEngine
import lib.Deque
import types

from datetime import datetime

try:
	import serial
	import Serial
except ImportError:
	serial = None
try:
	from Queue import *
except ImportError:
	from queue import *
try:
	import tkMessageBox
	from TKinter import *
except ImportError:
	from tkinter import *
	import tkinter.messagebox as tkMessageBox

from CNC import END_RUN_MACRO, RUN_MACRO, WAIT, MSG, UPDATE, WCS, CNC, GCode
import Utils
import Pendant
from _GenericGRBL import ERROR_CODES
from RepeatEngine import RepeatEngine
from Table import Table

WIKI = "https://github.com/vlachoudis/bCNC/wiki"

SERIAL_POLL    = 0.03	# s
OVERRIDE_POLL  = 0.06
SERIAL_TIMEOUT = 0.04	# s
G_POLL	       = 10	# s
RX_BUFFER_SIZE = 512
GCODE_POLL = 0.1
WRITE_THREAD_PERIOD = 0.016 #s

GPAT	  = re.compile(r"[A-Za-z]\s*[-+]?\d+.*")
FEEDPAT   = re.compile(r"^(.*)[fF](\d+\.?\d+)(.*)$")

CONNECTED     = "Connected"
NOT_CONNECTED = "Not connected"

STATECOLORDEF = "LightYellow" #Default color for unknown types?
STATECOLOR = {
		"Idle"		: "Yellow",
		"Run"		: "LightGreen",
		"Alarm"		: "Red",
		"Jog"		: "Green",
		"Home"		: "Green",
		"Check"		: "Magenta2",
		"Sleep"		: "LightBlue",
		"Hold"		: "Orange",
		"Hold:0"	: "Orange",
		"Hold:1"	: "OrangeRed",
		"Queue"		: "OrangeRed",
		"Door"		: "Red",
		"Door:0"	: "OrangeRed",
		"Door:1"	: "Red",
		"Door:2"	: "Red",
		"Door:3"	: "OrangeRed",
		CONNECTED	: "Yellow",
		NOT_CONNECTED	: "OrangeRed"
		}


		

#==============================================================================
# bCNC Sender class
#==============================================================================
class Sender:
	# Messages types for log Queue
	MSG_BUFFER  =  0	# write to buffer one command
	MSG_SEND    =  1	# send message
	MSG_RECEIVE =  2	# receive message from controller
	MSG_OK	    =  3	# ok response from controller, move top most command to terminal
	MSG_ERROR   =  4	# error message or exception
	MSG_RUNEND  =  5	# run ended
	MSG_CLEAR   =  6	# clear buffer

	def __init__(self):
		# Global variables
		self.history	 = []
		self._historyPos = None

		#self.mcontrol     = None
		self.controllers = {}
		self.controllerLoad()
		self.controllerSet("GRBL1")

		CNC.loadConfig(Utils.config)
		self.gcode = GCode()
		self.cnc   = self.gcode.cnc
		self.gcode.repeatEngine.app = self
		self.workTable = Table("WorkTable.csv")
		self.toolTable = Table("ToolTable.csv")
		self.compensationTable = Table("CompensationTable.csv")

		self.log	 = Queue()	# Log queue returned from GRBL
		self.deque	 = lib.Deque.Deque()	# Command queue to be send to GRBL
		self.pendant	 = Queue()	# Command queue to be executed from Pendant
		self.serial	 = None
		self.writeThread= None
		self.readThread= None
		self.writeRTThread = None
		self.repeatLock = threading.Lock()
		self.macrosRunning = 0
		self.processEngine = ProcessEngine.ProcessEngine(self)

		self._updateChangedState = time.time()
		self._posUpdate  = False	# Update position
		self._probeUpdate= False	# Update probe
		self._gUpdate	 = False	# Update $G
		self._update	 = None		# Generic update

		self.running	 = False
		self.runningPrev = None
		self.cleanAfter  = False
		self._runLines	 = 0
		self._quit	 = 0		# Quit counter to exit program
		self._stop	 = False	# Raise to stop current run
		self._pause	 = False	# machine is on Hold
		self._alarm	 = True		# Display alarm message if true
		self._msg	 = None
		self._sumcline	 = 0
		self._lastFeed	 = 0
		self._newFeed	 = 0

		self._onStart    = ""
		self._onStop     = ""

	#----------------------------------------------------------------------
	def controllerLoad(self):
		# Find plugins in the controllers directory and load them
		for f in glob.glob("%s/controllers/*.py"%(Utils.prgpath)):
			name,ext = os.path.splitext(os.path.basename(f))
			if name[0] == '_': continue
			#print("Loaded motion controller plugin: %s"%(name))
			try:
				exec("import %s"%(name))
				self.controllers[name] = eval("%s.Controller(self)"%(name))
			except (ImportError, AttributeError):
				typ, val, tb = sys.exc_info()
				traceback.print_exception(typ, val, tb)

	#----------------------------------------------------------------------
	def controllerList(self):
		#print("ctrlist")
		#self.controllers["GRBL1"].test()
		#if len(self.controllers.keys()) < 1: self.controllerLoad()
		return sorted(self.controllers.keys())

	#----------------------------------------------------------------------
	def controllerSet(self, ctl):
		#print("Activating motion controller plugin: %s"%(ctl))
		if ctl in self.controllers.keys():
			self.controller = ctl
			CNC.vars["controller"] = ctl
			self.mcontrol = self.controllers[ctl]
			#self.mcontrol.test()


	#----------------------------------------------------------------------
	def quit(self, event=None):
		self.saveConfig()
		Pendant.stop()

	#----------------------------------------------------------------------
	def loadConfig(self):
		self.controllerSet(Utils.getStr("Connection", "controller"))
		Pendant.port	 = Utils.getInt("Connection","pendantport",Pendant.port)
		GCode.LOOP_MERGE = Utils.getBool("File","dxfloopmerge")
		self.loadHistory()

	#----------------------------------------------------------------------
	def saveConfig(self):
		self.saveHistory()

	#----------------------------------------------------------------------
	def loadHistory(self):
		try:
			f = open(Utils.hisFile,"r")
		except:
			return
		self.history = [x.strip() for x in f]
		f.close()

	#----------------------------------------------------------------------
	def saveHistory(self):
		try:
			f = open(Utils.hisFile,"w")
		except:
			return
		f.write("\n".join(self.history))
		f.close()

	#----------------------------------------------------------------------
	# Evaluate a line for possible expressions
	# can return a python exception, needs to be catched
	#----------------------------------------------------------------------
	def evaluate(self, line):
		return self.gcode.evaluate(CNC.compileLine(line,True), self)

	#----------------------------------------------------------------------
	# Execute a line as gcode if pattern matches
	# @return True on success
	#	  False otherwise
	#----------------------------------------------------------------------
	def executeGcode(self, line):
		def send(line):
			if isinstance(line, tuple) or \
			   line[0] in ("$","!","~","?","(","@") or GPAT.match(line):
				self.sendGCode(line)
				return True
			return False
		if isinstance(line, list):
			for w in line:
				send(w)
			return True
		return send(line)

	#----------------------------------------------------------------------
	# Execute a single command
	#----------------------------------------------------------------------
	def executeCommand(self, line):
		#print
		#print "<<<",line
		#try:
		#	line = self.gcode.evaluate(CNC.compileLine(line,True))
		#except:
		#	return "Evaluation error", sys.exc_info()[1]
		#print ">>>",line

		if line is None: return

		oline = line.strip()
		line  = oline.replace(","," ").split()
		cmd   = line[0].upper()

		# ABS*OLUTE: Set absolute coordinates
		if rexx.abbrev("ABSOLUTE",cmd,3):
			self.sendGCode("G90")

		# HELP: open browser to display help
		elif cmd == "HELP":
			self.help()

		# HOME: perform a homing cycle
		elif cmd == "HOME":
			self.home()

		# LO*AD [filename]: load filename containing g-code
		elif rexx.abbrev("LOAD",cmd,2):
			self.load(line[1])

		# OPEN: open serial connection to grbl
		# CLOSE: close serial connection to grbl
		elif cmd in ("OPEN","CLOSE"):
			self.openClose()

		# QU*IT: quit program
		# EX*IT: exit program
		elif rexx.abbrev("QUIT",cmd,2) or rexx.abbrev("EXIT",cmd,2):
			self.quit()

		# PAUSE: pause cycle
		elif cmd == "PAUSE":
			self.pause()

		# RESUME: resume
		elif cmd == "RESUME":
			self.resume()

		# FEEDHOLD: feedhold
		elif cmd == "FEEDHOLD":
			self.feedHold()

		# REL*ATIVE: switch to relative coordinates
		elif rexx.abbrev("RELATIVE",cmd,3):
			self.sendGCode("G91")

		# RESET: perform a soft reset to grbl
		elif cmd == "RESET":
			self.softReset()

		# RUN: run g-code
		elif cmd == "RUN":
			self.run()

		# SAFE [z]: safe z to move
		elif cmd=="SAFE":
			try: CNC.vars["safe"] = float(line[1])
			except: pass
			self.statusbar["text"] = "Safe Z= %g"%(CNC.vars["safe"])

		# SA*VE [filename]: save to filename or to default name
		elif rexx.abbrev("SAVE",cmd,2):
			if len(line)>1:
				self.save(line[1])
			else:
				self.saveAll()

		# SENDHEX: send a hex-char in grbl
		elif cmd == "SENDHEX":
			self.sendHex(line[1])

		# SET [x [y [z]]]: set x,y,z coordinates to current workspace
		elif cmd == "SET":
			try: x = float(line[1])
			except: x = None
			try: y = float(line[2])
			except: y = None
			try: z = float(line[3])
			except: z = None
			self._wcsSet(x,y,z)

		elif cmd == "SETP":
			try: wcs = int(line[1])
			except: wcs = None
			try: x = float(line[2])
			except: x = None
			try: y = float(line[3])
			except: y = None
			try: z = float(line[4])
			except: z = None
			self._wcsSet(x,y,z, wcsIndex=wcs)

		elif cmd == "SET0":
			self._wcsSet(0.,0.,0.)

		elif cmd == "SETX":
			try: x = float(line[1])
			except: x = ""
			self._wcsSet(x,None,None)

		elif cmd == "SETY":
			try: y = float(line[1])
			except: y = ""
			self._wcsSet(None,y,None)

		elif cmd == "SETZ":
			try: z = float(line[1])
			except: z = ""
			self._wcsSet(None,None,z)

		elif cmd == "ACTIVATE":
			index = int(line[1])
			self.sendGCode("M64 P{}".format(index))

		elif cmd == "DEACTIVATE":
			index = int(line[1])
			self.sendGCode("M65 P{}".format(index))

		# STOP: stop current run
		elif cmd == "STOP":
			self.stopRun()

		elif cmd == "SETLZ":
			try: 
				z = float(line[1])
				self.sendGCode("$132={}".format(z))
				self.modifyConfiguration("$132", z)
			except:
				pass

		elif cmd == "MODIFY":
			try: 
				index = int(line[1])
				value = line[2]
				self.sendGCode("${}={}".format(index, value))
				self.modifyConfiguration("${}".format(index), value)
			except:
				pass

		# UNL*OCK: unlock grbl
		elif rexx.abbrev("UNLOCK",cmd,3):
			self.unlock()

		# Send commands to SMOOTHIE
		elif self.mcontrol.executeCommand(oline, line, cmd):
			pass

		else:
			return _("unknown command"),_("Invalid command %s")%(oline)

	def _getIndex(self, line):
		index = line[1:line.find('=')]
		return index.strip()

	#----------------------------------------------------------------------
	def modifyConfiguration(self, name, value): # should be done on Utils
		settingsFile = open("Settings.txt",'r')
		lines = settingsFile.readlines()
		settingsFile.close()
		name = self._getIndex(name + '=' + value)
		for id,w in enumerate(lines):
			if str(self._getIndex(w)) == str(name):
				lines[id] = w[:w.find('=')] + "= {}\n".format(value)
		settingsFile = open("Settings.txt",'w')
		settingsFile.writelines(lines)
		settingsFile.close()

	#----------------------------------------------------------------------
	def help(self, event=None):
		webbrowser.open(WIKI,new=2)

	#----------------------------------------------------------------------
	def loadRecent(self, recent):
		filename = Utils.getRecent(recent)
		if filename is None: return
		self.load(filename)

	#----------------------------------------------------------------------
	def _loadRecent0(self,event): self.loadRecent(0)

	# ----------------------------------------------------------------------
	def _loadRecent1(self,event): self.loadRecent(1)

	# ----------------------------------------------------------------------
	def _loadRecent2(self,event): self.loadRecent(2)

	# ----------------------------------------------------------------------
	def _loadRecent3(self,event): self.loadRecent(3)

	# ----------------------------------------------------------------------
	def _loadRecent4(self,event): self.loadRecent(4)

	# ----------------------------------------------------------------------
	def _loadRecent5(self,event): self.loadRecent(5)

	# ----------------------------------------------------------------------
	def _loadRecent6(self,event): self.loadRecent(6)

	# ----------------------------------------------------------------------
	def _loadRecent7(self,event): self.loadRecent(7)

	# ----------------------------------------------------------------------
	def _loadRecent8(self,event): self.loadRecent(8)

	# ----------------------------------------------------------------------
	def _loadRecent9(self,event): self.loadRecent(9)

	#----------------------------------------------------------------------
	def _saveConfigFile(self, filename=None):
		if filename is None:
			filename = self.gcode.filename
		Utils.setUtf("File", "dir",   os.path.dirname(os.path.abspath(filename)))
		Utils.setUtf("File", "file",  os.path.basename(filename))
		Utils.setUtf("File", "probe", os.path.basename(self.gcode.probe.filename))

	#----------------------------------------------------------------------
	# Load a file into editor
	#----------------------------------------------------------------------
	def load(self, filename):
		fn,ext = os.path.splitext(filename)
		ext = ext.lower()
		if ext==".probe":
			if filename is not None:
				self.gcode.probe.filename = filename
				self._saveConfigFile()
			self.gcode.probe.load(filename)
		elif ext == ".orient":
			# save orientation file
			self.gcode.orient.load(filename)
		elif ext == ".stl" or ext == ".ply":
			# FIXME: implements solid import???
			try :
				import tkMessageBox
				tkMessageBox.showinfo("Open 3D Mesh", "Importing of 3D mesh files in .STL and .PLY format is supported by SliceMesh plugin.\nYou can find it in CAM->SliceMesh.")
			except Exception as e :
				import tkinter
				import tkinter.messagebox
				tkinter.messagebox.showinfo("Open 3D Mesh", "Importing of 3D mesh files in .STL and .PLY format is supported by SliceMesh plugin.\nYou can find it in CAM->SliceMesh.")
		elif ext==".dxf":
			self.gcode.init()
			self.gcode.importDXF(filename)
			self._saveConfigFile(filename)
		elif ext==".svg":
			self.gcode.init()
			self.gcode.importSVG(filename)
			self._saveConfigFile(filename)
		else:
			self.gcode.load(filename)
			self._saveConfigFile()
		Utils.addRecent(filename)

	#----------------------------------------------------------------------
	def save(self, filename):
		fn,ext = os.path.splitext(filename)
		ext = ext.lower()
		if ext == ".probe" or ext == ".xyz":
			# save probe
			if not self.gcode.probe.isEmpty():
				self.gcode.probe.save(filename)
			if filename is not None:
				self._saveConfigFile()
		elif ext == ".orient":
			# save orientation file
			self.gcode.orient.save(filename)
		elif ext == ".stl":
			#save probe as STL
			self.gcode.probe.saveAsSTL(filename)
		elif ext == ".dxf":
			return self.gcode.saveDXF(filename)
		elif ext == ".svg":
			return self.gcode.saveSVG(filename)
		elif ext == ".txt":
			#save gcode as txt (only enabled blocks and no bCNC metadata)
			return self.gcode.saveTXT(filename)
		else:
			if filename is not None:
				self.gcode.filename = filename
				self._saveConfigFile()
			Utils.addRecent(self.gcode.filename)
			return self.gcode.save()

	#----------------------------------------------------------------------
	def saveAll(self, event=None):
		if self.gcode.filename:
			self.save(self.gcode.filename)
			if self.gcode.probe.filename:
				self.save(self.gcode.probe.filename)
		return "break"

	#----------------------------------------------------------------------
	# Serial write
	#----------------------------------------------------------------------
	def serial_write(self, data):
#		print('W %s : %s'%(type(data),data))

		#if sys.version_info[0] == 2:
		#	ret = self.serial.write(str(data))
		if isinstance(data, bytes):
			ret = self.serial.write(data)
		else:
			ret = self.serial.write(data.encode())
		return ret

	#----------------------------------------------------------------------
	# Open serial port
	#----------------------------------------------------------------------
	def open(self, device, baudrate):
		#self.serial = serial.Serial(
		self.serial = Serial.Serial(
						device.replace('\\', '\\\\'), #Escape for windows
						baudrate,
						bytesize=serial.EIGHTBITS,
						parity=serial.PARITY_NONE,
						stopbits=serial.STOPBITS_TWO,
						timeout=SERIAL_TIMEOUT,
						xonxoff=False,
						rtscts=False)
		time.sleep(0.2)
		CNC.vars["state"] = CONNECTED
		CNC.vars["color"] = STATECOLOR[CNC.vars["state"]]
		#self.state.config(text=CNC.vars["state"],
		#		background=CNC.vars["color"])
		# toss any data already received, see
		# http://pyserial.sourceforge.net/pyserial_api.html#serial.Serial.flushInput
		self.serial.flushInput()
		self.serial_write("\n\n")
		self._gcount = 0
		self._alarm  = True
		self.writeThread  = threading.Thread(target=self.serialIOWrite)
		self.writeRTThread  = threading.Thread(target=self.serialIOWriteRT)
		self.readThread = threading.Thread(target=self.serialIORead)
		self.writeThread.start()
		self.writeRTThread.start()
		self.readThread.start()
		return True

	#----------------------------------------------------------------------
	# Close serial port
	#----------------------------------------------------------------------
	def close(self):
		if self.serial is None: return
		try:
			self.stopRun()
		except:
			pass
		self._runLines = 0
		self.writeThread = None
		self.writeRTThread = None
		self.readThread = None
		time.sleep(1)
		try:
			self.serial.close()
		except:
			pass
		self.serial = None
		CNC.vars["state"] = NOT_CONNECTED
		CNC.vars["color"] = STATECOLOR[CNC.vars["state"]]

	#----------------------------------------------------------------------
	# Send to controller a gcode or command
	# WARNING: it has to be a single line!
	#----------------------------------------------------------------------
	def sendGCode(self, cmd):
		if self.serial and not self.running:
			if isinstance(cmd,tuple):
				self.deque.append(cmd)
			elif isinstance(cmd, str):
				self.deque.append(cmd+"\n")
			else:
				for w in cmd:
					self.sendGCode(w)
			return True
		return False

	#----------------------------------------------------------------------
	def sendHex(self, hexcode):
		if self.serial is None: return
		self.serial_write(chr(int(hexcode,16)))
		self.serial.flush()

	#----------------------------------------------------------------------
	# FIXME: legacy wrappers. try to call mcontrol directly instead:
	#----------------------------------------------------------------------
	def hardReset(self):			self.mcontrol.hardReset()
	def softReset(self, clearAlarm=True):	self.mcontrol.softReset(clearAlarm)
	def unlock(self, clearAlarm=True):	self.mcontrol.unlock(clearAlarm)
	def home(self, event=None):		self.mcontrol.home(event)
	def viewSettings(self):			self.mcontrol.viewSettings()
	def viewParameters(self):		self.mcontrol.viewParameters()
	def viewState(self):			self.mcontrol.viewState()
	def viewBuild(self):			self.mcontrol.viewBuild()
	def viewStartup(self):			self.mcontrol.viewStartup()
	def checkGcode(self):			self.mcontrol.checkGcode()
	def grblHelp(self):			self.mcontrol.grblHelp()
	def grblRestoreSettings(self):		self.mcontrol.grblRestoreSettings()
	def grblRestoreWCS(self):		self.mcontrol.grblRestoreWCS()
	def grblRestoreAll(self):		self.mcontrol.grblRestoreAll()
	def goto(self, x=None, y=None, z=None):	self.mcontrol.goto(x,y,z)
	def _wcsSet(self, x, y, z, a=None, b=None, c=None, wcsIndex=None):		self.mcontrol._wcsSet(x,y,z,wcsIndex=wcsIndex) # FIXME Duplicate with ControlPage
	def feedHold(self, event=None):		self.mcontrol.feedHold(event)
	def resume(self, event=None):		self.mcontrol.resume(event)
	def pause(self, event=None):		self.mcontrol.pause(event)
	def purgeController(self):		self.mcontrol.purgeController()
	def g28Command(self):			self.sendGCode("G28.1") #FIXME: ???
	def g30Command(self):			self.sendGCode("G30.1") #FIXME: ???

	#----------------------------------------------------------------------
	def emptyDeque(self):
		self.deque.clear()

	#----------------------------------------------------------------------
	def stopProbe(self):
		if self.gcode.probe.start:
			self.gcode.probe.clear()

	#----------------------------------------------------------------------
	def getBufferFill(self):
		return self._sumcline * 100. / RX_BUFFER_SIZE

	#----------------------------------------------------------------------
	def initRun(self):
		self._quit   = 0
		self._pause  = False
		self._paths  = None
		self.running = True
		self.macrosRunning = 0
		self.disable()
		self.emptyDeque()
		time.sleep(1)

	#----------------------------------------------------------------------
	# Called when run is finished
	#----------------------------------------------------------------------
	def runEnded(self):
		if self.running:
			self.log.put((Sender.MSG_RUNEND,_("Run ended")))
			self.log.put((Sender.MSG_RUNEND, str(datetime.now())))
			self.log.put((Sender.MSG_RUNEND, str(CNC.vars["msg"])))
			if self.gcode.repeatEngine.isRepeatable():
				self.after(50, self.repeatProgram)
			else:
				self.after(1000, self.purgeController)

			if self._onStop:
				try:
					os.system(self._onStop)
				except:
					pass

		self._runLines = 0
		self._quit     = 0
		self._msg      = None
		self._pause    = False
		self.running   = False
		self.macrosRunning = 0
		CNC.vars["running"] = False
		CNC.vars["pgmEnd"] = False


	#----------------------------------------------------------------------
	# Stop the current run
	#----------------------------------------------------------------------
	def stopRun(self, event=None):
		self.feedHold()
		self.emptyDeque()
		self.gcode.repeatEngine.cleanState()
		if self.repeatLock is not None:
			if not self.repeatLock.locked():
				self.repeatLock.acquire()
		self.emptyDeque()
		self._stop = True
		self.purgeController()

	#----------------------------------------------------------------------
	# This should be called everytime that milling of g-code file is finished
	# So we can purge the controller for the next job
	# See https://github.com/vlachoudis/bCNC/issues/1035
	#----------------------------------------------------------------------
	def jobDone(self):
		print("Job done. Purging the controller. (Running: %s)"%(self.running))
		#self.purgeController()

	def repeatProgram(self):
		def th():
			self.sendGCode((WAIT,))
			time.sleep(self.gcode.repeatEngine.TIMEOUT_TO_REPEAT/1000)
			if self.repeatLock.locked():
				self.repeatLock.release()
				return
			self.event_generate("<<Run>>", when="tail")
		threading.Thread(target=th).start()

	#----------------------------------------------------------------------
	# This is called everytime that motion controller changes the state
	# YOU SHOULD PASS ONLY REAL HW STATE TO THIS, NOT BCNC STATE
	# Right now the primary idea of this is to detect when job stopped running
	#----------------------------------------------------------------------
	def controllerStateChange(self, state):
		print("Controller state changed to: %s (Running: %s)"%(state, self.running))
		if state in ("Idle"):
			if time.time() - self._updateChangedState > 20:
				self.mcontrol.viewParameters()
				self.mcontrol.viewState()
				self._updateChangedState = time.time()

		if self.cleanAfter == True and self.running == False and state in ("Idle"):
			self.cleanAfter = False
			self.jobDone()

	def serialIORead(self):
		self._cline = []
		self._sline = []
		buff = ""
		while self.readThread:
			time.sleep(0.0001)
			# Anything to receive?
			try:
				line = str(self.serial.read().decode())
				for w in line:
					if w != '':
						buff += w
			except:
				self.log.put((Sender.MSG_RECEIVE, str(sys.exc_info()[1])))
			if (index:=buff.find('\n'))!=-1:
				line = buff[:index+1].strip()
				buff = buff[index+1:]
			else:
				continue
			if self.mcontrol.parseLine(line, self._cline, self._sline):
				pass
			else:
				self.log.put((Sender.MSG_RECEIVE, line))

	#----------------------------------------------------------------------
	# thread performing I/O on serial line
	#----------------------------------------------------------------------
	def serialIOWriteRT(self):
		self.sio_count = 0
		tr = tg = to = time.time()		# last time a ? or $G was send to grbl
		while self.writeRTThread:
			time.sleep(WRITE_THREAD_PERIOD)
			t = time.time()
			# refresh machine position?
			if t-tr > SERIAL_POLL and self.sio_count<10:
				self.sio_count += 1
				self.mcontrol.viewStatusReport()
				tr = t

				#If Override change, attach feed
			if t-to > OVERRIDE_POLL:
				to = t
				self.mcontrol.overrideSet()

	#----------------------------------------------------------------------
	# Helper functions for serialIOWrite
	#----------------------------------------------------------------------
	def shouldSend(self):
		return not self.sio_wait and not self._pause

	def hasNewCommand(self):
		return len(self.deque)!=0

	def shouldSkipCommand(self, cmd):
		line = cmd.src
		if not isinstance(line, str): return False
		line = line.upper()
		if CNC.vars["SafeDoor"]:
			if "M3" in line or "M4" in line:
				return True
		return False

	def getNextCommand(self):
		return self.deque.popleft()

	def isInternalStrCommand(self, code):
		return False

	def isInternalCommand(self, cmd):
		code = cmd.src
		if isinstance(code, tuple): return True
		elif isinstance(code, str):
			return self.isInternalStrCommand(code)
		return False

	def executeTupleInternalCommand(self, code):
		id = code[0]
		if len(code)==2:
			value = code[1]
		else:
			value = None
		if id == WAIT:
			self.sio_wait = True
		elif id == MSG:
			self._gcount += 1
			if value is not None:
				self._msg = value
		elif id == UPDATE:
			self._gcount += 1
			self._update = value
		elif id == RUN_MACRO:
			self.macrosRunning += 1
		elif id == END_RUN_MACRO:
			self.macrosRunning -= 1
		else:
			self._gcount += 1

	def executeStrInternalCommand(self, code):
		pass

	def isRunningMacro(self):
		return self.macrosRunning > 0


	def executeInternalCommand(self, cmd):
		code = cmd.src
		if isinstance(code, tuple): return self.executeTupleInternalCommand(code)
		return self.executeStrInternalCommand(code)

	def waitWhileRxBufferFull(self):
		while sum(self._cline) >= RX_BUFFER_SIZE:
			time.sleep(0.001)

	def isRxBufferFull(self):
		return sum(self._cline) >= RX_BUFFER_SIZE

	def _checkAndEvaluateStop(self):
		if self._stop:
			self.emptyDeque()
			self.macrosRunning = 0
			self.log.put((Sender.MSG_CLEAR, ""))
			# WARNING if runLines==maxint then it means we are
			# still preparing/sending lines from from bCNC.run(),
			# so don't stop
			if self._runLines != sys.maxsize:
				self._stop = False
			return True
		return False


	def appendCodeToDeque(self, cmds):
		"""
			Apend code to the front of self.deque. Everything is a macro here.
		Args:
		    cmds (): list of commands to append
		"""
		if cmds is None: return
		if not isinstance(cmds, list): 
			cmds = [cmds]
		if len(cmds) == 0:
			self._runLines -= 1 # remove line from path
			return
		self._runLines += len(cmds) - 1 # consider that is already added to _runLines
		self.deque.appendleft((END_RUN_MACRO,))
		while len(cmds):
			self.deque.appendleft(cmds[-1])
			del cmds[-1]
		self.deque.appendleft((RUN_MACRO,))

	def process(self, pNode):
		cmds = pNode.process()
		self.appendCodeToDeque(cmds)

	#----------------------------------------------------------------------
	# thread performing I/O on serial line
	#----------------------------------------------------------------------
	def serialIOWrite(self):
		self.sio_wait   = False		# wait for commands to complete (status change to Idle)
		self.sio_status = False		# waiting for status <...> report
		self._cline  = []		# length of pipeline commands
		self._sline  = []			# pipeline commands
		self.macrosRunning = 0
		toSend = None			# next string to send
		processNode = None

		while self.writeThread:
			time.sleep(WRITE_THREAD_PERIOD)

			if self._checkAndEvaluateStop():
				continue

			if not self.shouldSend():
				continue

			if processNode is not None:
				self.process(processNode)
				processNode = None
				continue

			toSend = None
			if self.hasNewCommand():
				toSend = Command.cmdFactory(self.getNextCommand())
			else:
				continue

			if self.shouldSkipCommand(toSend): 
				# TODO: This can be done inside Command class
				# or in the Process class
				continue

			if self.isInternalCommand(toSend): # TODO: This should be an ProcessNode
				self.executeInternalCommand(toSend)
				continue

			processNode = self.processEngine.getValidProcessNode(toSend)
			if processNode is not None:
				processNode.preprocessCommand(toSend)
				if processNode.shouldWait:
					self.executeInternalCommand(Command.Command((WAIT,)))
					self._runLines += 1
					continue
				self.process(processNode)
				processNode = None
				continue

			if self._checkAndEvaluateStop():
				continue

			self._sline.append(toSend.src)
			self._cline.append(len(toSend.src))

			hasStoped = False
			while self.isRxBufferFull():
				time.sleep(0.001)
				if self._checkAndEvaluateStop():
					hasStoped = True
					break
			if hasStoped:
				continue

			self._sumcline = sum(self._cline)
			self.serial_write(toSend.src)
			self.serial.flush()
			self.log.put((Sender.MSG_SEND, toSend.src))
