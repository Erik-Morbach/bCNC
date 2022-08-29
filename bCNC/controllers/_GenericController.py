# Generic motion controller definition
# All controller plugins inherit features from this one

from __future__ import absolute_import
from __future__ import print_function

from CNC import CNC, WCS
from CNCRibbon    import Page
import os.path
import time
import re

#GRBLv1
SPLITPAT  = re.compile(r"[:,]")

#GRBLv0 + Smoothie
STATUSPAT = re.compile(r"^<(\w*?),MPos:([+\-]?\d*\.\d*),([+\-]?\d*\.\d*),([+\-]?\d*\.\d*)(?:,[+\-]?\d*\.\d*)?(?:,[+\-]?\d*\.\d*)?(?:,[+\-]?\d*\.\d*)?,WPos:([+\-]?\d*\.\d*),([+\-]?\d*\.\d*),([+\-]?\d*\.\d*)(?:,[+\-]?\d*\.\d*)?(?:,[+\-]?\d*\.\d*)?(?:,[+\-]?\d*\.\d*)?(?:,.*)?>$")
POSPAT	  = re.compile(r"^\[(...):([+\-]?\d*\.\d*),([+\-]?\d*\.\d*),([+\-]?\d*\.\d*)(?:,[+\-]?\d*\.\d*)?(?:,[+\-]?\d*\.\d*)?(?:,[+\-]?\d*\.\d*)?(:(\d*))?\]$")
TLOPAT	  = re.compile(r"^\[(...):([+\-]?\d*\.\d*)\]$")
DOLLARPAT = re.compile(r"^\[G\d* .*\]$")

#Only used in this file
VARPAT    = re.compile(r"^\$(\d+)=(\d*\.?\d*) *\(?.*")

class _GenericController:
	def test(self):
		print("test supergen")

	def executeCommand(self, oline, line, cmd):
		return False

	def hardResetPre(self):
		pass

	def hardResetAfter(self):
		pass

	def viewStartup(self):
		pass

	def checkGcode(self):
		pass

	def viewSettings(self):
		pass

	def grblRestoreSettings(self):
		pass

	def grblRestoreWCS(self):
		pass

	def grblRestoreAll(self):
		pass

	def purgeControllerExtra(self):
		pass

	def overrideSet(self):
		pass

	def hardReset(self):
		self.master.busy()
		if self.master.serial is not None:
			self.hardResetPre()
			self.master.openClose()
			self.hardResetAfter()
		self.master.openClose()
		self.master.stopProbe()
		self.master._alarm = False
		CNC.vars["_OvChanged"] = True	# force a feed change if any
		self.master.notBusy()
		self.sendSettings()
		self.sendParameters()
		self.viewParameters()

	#----------------------------------------------------------------------
	def softReset(self, clearAlarm=True):
		if self.master.serial:
			self.master.serial_write(b"\x18")
		self.master.stopProbe()
		if clearAlarm: self.master._alarm = False
		CNC.vars["_OvChanged"] = True	# force a feed change if any
		self.sendSettings()
		self.sendParameters()
		self.viewParameters()

	#----------------------------------------------------------------------
	def unlock(self, clearAlarm=True):
		if clearAlarm: self.master._alarm = False
		self.master.sendGCode("$X")
		self.sendSettings()
		self.sendParameters()
		self.master.sendGCode("$X")
		self.sendSettings()
		self.sendParameters()

	#----------------------------------------------------------------------
	def home(self, event=None):
		self.master._alarm = False
		self.master.sendGCode("$H")

	def viewStatusReport(self):
		self.master.serial_write(b'?')
		self.master.sio_status = True

	def viewConfiguration(self):
		self.master.sendGcode("$$")

	def saveSettings(self):
		flag = 'x'
		if os.path.isfile("Settings.txt"):
			return
		with open("Settings.txt", flag) as file:
			file.write("$0 = 5\n")

	def sendSettings(self):
		settings = self.getSettings()
		for settingsUnit in settings:
			self.master.sendGCode(settingsUnit)
			if "G7" in settingsUnit:
				CNC.vars["radius"] = "G7"

	def getSettings(self):
		if not os.path.isfile("Settings.txt"):
			self.saveSettings()
		settings = []
		with open("Settings.txt", 'r') as settingsFile:
			for line in settingsFile.readlines():
				settings += [line]
		return settings

	def viewParameters(self):
		self.master.sendGCode("$#")

	def getParameters(self):
		axis = "XYZABC"
		if not os.path.isfile("WorkCoordinates.txt"):
			self.saveParameters()
				
		workPositions = {}
		with open("WorkCoordinates.txt", 'r') as workFile:
			for line in workFile.readlines():
				positions = line.split(' ')
				if len(positions) < 7:
					continue
				positions[-1] = positions[-1].replace('\n','')
				positionIndex = int(positions[0])
				positions = positions[1:]
				radiusMode = "G90"
				if len(positions) == 7:
					radiusMode = positions[6]
					del positions[-1]
				workPositions[positionIndex] = {}
				workPositions[positionIndex]["R"] = radiusMode
				for (index, currentAxis) in enumerate(axis):
					workPositions[positionIndex][currentAxis] = positions[index]
		return workPositions

	def saveParameters(self, workPositions=None):
		axis = "XYZABC"
		if workPositions == None:
			workPositions = {}
		flag = 'x'
		if os.path.isfile("WorkCoordinates.txt"):
			flag = 'w'

		with open("WorkCoordinates.txt",flag) as file:
			for workIndex in range(1, 9):
				file.write(str(workIndex))
				if workIndex not in workPositions.keys():
					workPositions[workIndex] = {}
					workPositions[workIndex]["R"] = "G90"
				for currentAxis in axis:
					if currentAxis not in workPositions[workIndex].keys():
						workPositions[workIndex][currentAxis] = "0"
					else:
						try:
							workPositions[workIndex][currentAxis] = str(float(workPositions[workIndex][currentAxis]))
						except:
							workPositions[workIndex][currentAxis] = "0"
					file.write(" {}".format(workPositions[workIndex][currentAxis]))
				file.write(" {}".format(workPositions[workIndex]["R"]))
				file.write("\n")
		
	def sendParameters(self):
		axis = "XYZABC"
		parameters = self.getParameters()
		time.sleep(0.05)
		currentMode = CNC.vars["radius"]
		for workIndex in range(1,9):
			self.master.sendGCode(parameters[workIndex]["R"])
			cmd = "G10L2P" + str(workIndex)
			for currentAxis in axis:
				cmd += currentAxis + parameters[workIndex][currentAxis]
			self.master.sendGCode(cmd)
		self.master.sendGCode(currentMode)

	def viewState(self): #Maybe rename to viewParserState() ???
		self.master.serial_write(b'?')

	#----------------------------------------------------------------------
	def jog(self, dir):
		#print("jog",dir)
		self.master.sendGCode("G91G0%s"%(dir))
		self.master.sendGCode("G90")

	#----------------------------------------------------------------------
	def goto(self, x=None, y=None, z=None, a=None, b=None, c=None):
		cmd = "G90G0"
		if x is not None: cmd += "X%g"%(x)
		if y is not None: cmd += "Y%g"%(y)
		if z is not None: cmd += "Z%g"%(z)
		if a is not None: cmd += "A%g"%(a)
		if b is not None: cmd += "B%g"%(b)
		if c is not None: cmd += "C%g"%(c)
		self.master.sendGCode("%s"%(cmd))

	#----------------------------------------------------------------------
	def _wcsSet(self, x, y, z, a=None, b=None, c=None, wcsIndex=None):
		
		# Updating WorkCoordinates.txt file
		parameters = self.getParameters()
		radiusMode = CNC.vars["radius"]

		#global wcsvar
		#p = wcsvar.get()
		if wcsIndex is None:
			p = WCS.index(CNC.vars["WCS"])
		else: p = wcsIndex

		parameters[p+1]["R"] = radiusMode
		if p<6:
			cmd = "G10L20P%d"%(p+1)
		elif p==6:
			cmd = "G28.1"
		elif p==7:
			cmd = "G30.1"
		elif p==8:
			cmd = "G92"

		pos = ""
		if x is not None and abs(float(x))<10000.0: 
			pos += "X"+str(x)
			parameters[p+1]['X'] = str(CNC.vars['mx'] - float(x))
		if y is not None and abs(float(y))<10000.0: 
			pos += "Y"+str(y)
			parameters[p+1]['Y'] = str(CNC.vars['my'] - float(y))
		if z is not None and abs(float(z))<10000.0: 
			pos += "Z"+str(z)
			parameters[p+1]['Z'] = str(CNC.vars['mz'] - float(z))
		if a is not None and abs(float(a))<10000.0: 
			pos += "A"+str(a)
			parameters[p+1]['A'] = str(CNC.vars['ma'] - float(a))
		if b is not None and abs(float(b))<10000.0: 
			pos += "B"+str(b)
			parameters[p+1]['B'] = str(CNC.vars['mb'] - float(b))
		if c is not None and abs(float(c))<10000.0: 
			pos += "C"+str(c)
			parameters[p+1]['C'] = str(CNC.vars['mc'] - float(c))
		cmd += pos
		self.master.sendGCode(cmd)

		self.saveParameters(parameters)


		self.viewParameters()
		self.master.event_generate("<<Status>>",
			data=(_("Set workspace %s to %s")%(WCS[p],pos)))
			#data=(_("Set workspace %s to %s")%(WCS[p],pos)))
		self.master.event_generate("<<CanvasFocus>>")

	#----------------------------------------------------------------------
	def feedHold(self, event=None):
		if event is not None and not self.master.acceptKey(True): return
		if self.master.serial is None: return
		self.master.serial_write(b'!')
		self.master.serial.flush()
		self.master._pause = True

	#----------------------------------------------------------------------
	def resume(self, event=None):
		if event is not None and not self.master.acceptKey(True): return
		if self.master.serial is None: return
		self.master.serial_write(b'~')
		self.master.serial.flush()
		self.master._msg   = None
		self.master._alarm = False
		self.master._pause = False

	#----------------------------------------------------------------------
	def pause(self, event=None):
		if self.master.serial is None: return
		if self.master._pause:
			self.master.resume()
		else:
			self.master.feedHold()

	#----------------------------------------------------------------------
	# Purge the buffer of the controller. Unfortunately we have to perform
	# a reset to clear the buffer of the controller
	#---------------------------------------------------------------------
	def purgeController(self):
		self.master.serial_write(b'!')
		self.master.serial.flush()
		time.sleep(1)
		# remember and send all G commands
		G = " ".join([x for x in CNC.vars["G"] if x[0]=="G"])	# remember $G
		TLO = CNC.vars["TLO"]
		self.softReset(False)			# reset controller
		self.purgeControllerExtra()
		self.master.runEnded()
		self.master.stopProbe()
		if G: self.master.sendGCode(G)			# restore $G
		self.master.sendGCode("G43.1Z%s"%(TLO))	# restore TLO
		self.viewState()


	#----------------------------------------------------------------------
	def displayState(self, state):
		state = state.strip()

		#Do not show g-code errors, when machine is already in alarm state
		if (CNC.vars["state"].startswith("ALARM:") and state.startswith("error:")):
			print("Supressed: %s"%(state))
			return

		# Do not show alarm without number when we already display alarm with number
		if (state == "Alarm" and CNC.vars["state"].startswith("ALARM:")):
			return

		CNC.vars["state"] = state


	#----------------------------------------------------------------------
	def parseLine(self, line, cline, sline):
		if not line:
			return True

		elif line[0]=="<":
			if not self.master.sio_status:
				self.master.log.put((self.master.MSG_RECEIVE, line))
			self.parseBracketAngle(line, cline)

		elif "pgm end" in line.lower():
			CNC.vars["pgmEnd"] = True

		elif line[0]=="[":
			self.master.log.put((self.master.MSG_RECEIVE, line))
			self.parseBracketSquare(line)

		elif "error:" in line or "ALARM:" in line:
			self.master.log.put((self.master.MSG_ERROR, line))
			self.master._gcount += 1
			#print "gcount ERROR=",self._gcount
			if cline: del cline[0]
			if sline: CNC.vars["errline"] = sline.pop(0)
			if not self.master._alarm: self.master._posUpdate = True
			self.master._alarm = True
			self.displayState(line)
			if self.master.running:
				self.master._stop = True

		elif line.find("ok")>=0:
			self.master.log.put((self.master.MSG_OK, line))
			self.master._gcount += 1
			if cline: del cline[0]
			if sline: del sline[0]
			#print "SLINE:",sline
#			if  self._alarm and not self.running:
#				# turn off alarm for connected status once
#				# a valid gcode event occurs
#				self._alarm = False

		elif line[0] == "$":
			self.master.log.put((self.master.MSG_RECEIVE, line))
			pat = VARPAT.match(line)
			if pat:
				CNC.vars["grbl_%s"%(pat.group(1))] = pat.group(2)

		elif line[:4]=="Grbl" or line[:13]=="CarbideMotion": # and self.running:
			#tg = time.time()
			self.master.log.put((self.master.MSG_RECEIVE, line))
			self.master._stop = True
			del cline[:]	# After reset clear the buffer counters
			del sline[:]
			CNC.vars["version"] = line.split()[1]
			# Detect controller
			if self.master.controller in ("GRBL0", "GRBL1"):
				self.master.controllerSet("GRBL%d"%(int(CNC.vars["version"][0])))

		else:
			#We return false in order to tell that we can't parse this line
			#Sender will log the line in such case
			return False

		#Parsing succesfull
		return True
