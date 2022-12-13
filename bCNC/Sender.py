# -*- coding: ascii -*-
# $Id: bCNC.py,v 1.6 2014/10/15 15:04:48 bnv Exp bnv $
#
# Author: Vasilis Vlachoudis
#  Email: vvlachoudis@gmail.com
#   Date: 17-Jun-2015

from __future__ import absolute_import
from __future__ import print_function

import requests
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

from datetime import datetime

try:
	import serial
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

from CNC import WAIT, MSG, UPDATE, WCS, CNC, GCode
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
		self.queue	 = Queue()	# Command queue to be send to GRBL
		self.pendant	 = Queue()	# Command queue to be executed from Pendant
		self.serial	 = None
		self.writeThread= None
		self.readThread= None
		self.repeatLock = threading.Lock()


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
		self._stopHomeTest = 0

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

	def isExpandable(self, line):
		if not isinstance(line, str): return False
		line = line.lower().replace(' ','')
		for i in range(1000,2000):
			if line.find('m%d' % i)!=-1:
				return True
		return False

	def expand(self, line):
		def getNextInt(line:str):
			aux = ""
			for w in line:
				if not w.isdigit():
					break
				aux += w
			return int(aux)
		mIndex = line.lower().find('m')
		if mIndex == -1:
			return line
		mCode = getNextInt(line[mIndex+1:])
		if mCode >= 1000:
			return CNC.macroM1XXX(mCode)
		return line

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

	def testHomeSingle(self):
		def wait():
			time.sleep(0.5)
			while not ("idle" in CNC.vars["state"].lower()):
				time.sleep(0.1)
			time.sleep(0.05)
			self.mcontrol.softReset()
			time.sleep(0.5)
		id = 0
		wait()
		self.sendGCode("$HZ")
		wait()
		self.sendGCode("G0Z-20")
		wait()
		self.sendGCode("$HX")
		wait()
		self.sendGCode("G0X-20Z-20")
		self.sendGCode("G0X-5Z-5")
		wait()
		response =  requests.get("http://192.168.4.1/Dros", timeout=2)
		response = response.json()
		print(response)
		axes = 'xyz'
		typ = 'wm'
		values = []
		for a in axes:
			for t in typ:
				values += [response[t+a]]
		values = struct.pack(len(values)*'q', *values)
		file = open("teste{}".format(id),'ab')
		file.write(values)
		file.close()

	def testHome(self, n):
		for _ in range(n):
			if self._stopHomeTest:
				self._stopHomeTest = 0
				break
			self.testHomeSingle()
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

		if cmd == "STOPHOME":
			self._stopHomeTest = 1

		elif cmd == "TEST":
			n = int(line[1])
			threading.Thread(target=self.testHome, args=(n,)).start()

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
	def modifyConfiguration(self, name, value):
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
		self.serial = serial.serial_for_url(
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
		self.readThread = threading.Thread(target=self.serialIORead)
		self.writeThread.start()
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
				self.queue.put(cmd, block=True)
			elif isinstance(cmd, str):
				self.queue.put(cmd+"\n", block=True)
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
	def emptyQueue(self):
		while self.queue.qsize()>0:
			try:
				self.queue.get_nowait()
			except Empty:
				break

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
		self.disable()
		self.emptyQueue()
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
		CNC.vars["running"] = False
		CNC.vars["pgmEnd"] = False


	#----------------------------------------------------------------------
	# Stop the current run
	#----------------------------------------------------------------------
	def stopRun(self, event=None):
		self._stop = True
		self.feedHold()
		self.gcode.repeatEngine.cleanState()
		self.purgeController()
		self.emptyQueue()
		if self.repeatLock is not None:
			if not self.repeatLock.locked():
				self.repeatLock.acquire()
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
		if self.repeatLock.locked():
			self.repeatLock.release()
			return
		self.executeCommand("%wait")
		while CNC.vars["state"].lower() in ["run", "hold"]:
			if self.repeatLock.locked(): 
				self.repeatLock.release()
				return
		time.sleep(self.gcode.repeatEngine.TIMEOUT_TO_REPEAT/1000)
		while CNC.vars["state"].lower() in ["run", "hold"]:
			if self.repeatLock.locked():
				self.repeatLock.release()
				return
		if CNC.vars["state"].lower() != "idle":
			return
		if self.gcode.repeatEngine.fromSD:
			pass
		else:
			self.event_generate("<<Run>>")
		if self.repeatLock.locked():
			self.repeatLock.release()

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
				line = str(self.serial.read(max(self.serial.in_waiting,1)).decode())
				buff += str(line)
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
	def serialIOWrite(self):
		self.sio_wait   = False		# wait for commands to complete (status change to Idle)
		self.sio_status = False		# waiting for status <...> report
		self.sio_count = 0
		self._cline  = []		# length of pipeline commands
		self._sline  = []			# pipeline commands
		tosend = None			# next string to send
		tr = tg = to = time.time()		# last time a ? or $G was send to grbl

		while self.writeThread:
			time.sleep(0.001)
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

			self.serial.flush()

			# Fetch new command to send if...
			if tosend is None and not self.sio_wait and not self._pause and self.queue.qsize()>0:
				try:
					tosend = self.queue.get_nowait()
					#print "+++",repr(tosend)
					if isinstance(tosend, tuple):
						#print "gcount tuple=",self._gcount
						# wait to empty the grbl buffer and status is Idle
						if tosend[0] == WAIT:
							# Don't count WAIT until we are idle!
							self.sio_wait = True
							#print "+++ WAIT ON"
							#print "gcount=",self._gcount, self._runLines
						elif tosend[0] == MSG:
							# Count executed commands as well
							self._gcount += 1
							if tosend[1] is not None:
								# show our message on machine status
								self._msg = tosend[1]
						elif tosend[0] == UPDATE:
							# Count executed commands as well
							self._gcount += 1
							self._update = tosend[1]
						else:
							# Count executed commands as well
							self._gcount += 1
						tosend = None

					elif not isinstance(tosend,str):
						try:
							tosend = self.gcode.evaluate(tosend, self)
#							if isinstance(tosend, list):
#								self._cline.append(len(tosend[0]))
#								self._sline.append(tosend[0])
							if isinstance(tosend,str):
								tosend += "\n"
							else:
								# Count executed commands as well
								self._gcount += 1
								#print "gcount str=",self._gcount
							#print "+++ eval=",repr(tosend),type(tosend)

						except:
							for s in str(sys.exc_info()[1]).splitlines():
								self.log.put((Sender.MSG_ERROR,s))
							self._gcount += 1
							tosend = None
				except Empty:
					break

				if tosend is not None:
					# All modification in tosend should be
					# done before adding it to self._cline

					# Keep track of last feed
					pat = FEEDPAT.match(tosend)
					if pat is not None:
						self._lastFeed = pat.group(2)

					# Modify sent g-code to reflect overrided feed for controllers without override support
					if not self.mcontrol.has_override:
						if CNC.vars["_OvChanged"]:
							CNC.vars["_OvChanged"] = False
							self._newFeed = float(self._lastFeed)*CNC.vars["_OvFeed"]/100.0
							if pat is None and self._newFeed!=0 \
							   and not tosend.startswith("$"):
								tosend = "f%g%s" % (self._newFeed, tosend)

						# Apply override Feed
						if CNC.vars["_OvFeed"] != 100 and self._newFeed != 0:
							pat = FEEDPAT.match(tosend)
							if pat is not None:
								try:
									tosend = "%sf%g%s\n" % \
										(pat.group(1),
										 self._newFeed,
										 pat.group(3))
								except:
									pass

					# Bookkeeping of the buffers
					self._sline.append(tosend)
					self._cline.append(len(tosend))
			# Received external message to stop
			if self._stop:
				self.emptyQueue()
				tosend = None
				self.log.put((Sender.MSG_CLEAR, ""))
				# WARNING if runLines==maxint then it means we are
				# still preparing/sending lines from from bCNC.run(),
				# so don't stop
				if self._runLines != sys.maxsize:
					self._stop = False

			if tosend is not None:
				if CNC.vars["SafeDoor"]:
					for w in ["M3", "M4"]:
						if w in str(tosend).upper():
							tosend = None
							break
			if tosend is not None and not self.running and t-tg > G_POLL:
				tg = t
				self.mcontrol.viewGState()
			#print "tosend='%s'"%(repr(tosend)),"stack=",self._sline,
			#	"sum=",sum(self._cline),"wait=",wait,"pause=",self._pause
			if tosend is not None and sum(self._cline) < RX_BUFFER_SIZE:
				self._sumcline = sum(self._cline)
#				if isinstance(tosend, list):
#					self.serial_write(str(tosend.pop(0)))
#					if not tosend: tosend = None

				#print ">S>",repr(tosend),"stack=",self._sline,"sum=",sum(self._cline)
				if self.mcontrol.gcode_case > 0: tosend = tosend.upper()
				if self.mcontrol.gcode_case < 0: tosend = tosend.lower()

				self.serial_write(tosend)

				self.log.put((Sender.MSG_SEND, tosend))

				tosend = None
