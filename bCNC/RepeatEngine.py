import tkinter
#==============================================================================
# BJM Repeat Commands Class 
#==============================================================================
class RepeatEngine:
	TYPE_NONE = 0
	TYPE_M47 = 1
	TYPE_M47P = 2
	TIMEOUT_TO_REPEAT = 0.5
	repeatType: int
	m30CounterLimit: tkinter.IntVar
	m30Counter: tkinter.IntVar
	app: any
	fromSD: bool
	def __init__(self, CNCRef):
		self.CNCRef = CNCRef
		self.m30Counter = tkinter.IntVar(value=0)
		self.m30CounterLimit = tkinter.IntVar(value=0)
		self.cleanState()

	def isRepeatable(self):
		if self.CNCRef.vars["barEnd"] == 0:
			return False
		if self.repeatType == self.TYPE_M47:
			return True
		if self.repeatType == self.TYPE_M47P and \
				self.m30Counter.get() < self.m30CounterLimit.get():
			return True
		return False

	def countRepetition(self):
		self.m30Counter.set(self.m30Counter.get() + 1)

	def cleanState(self):
		self.repeatType = self.TYPE_NONE

	def updateEngine(self, line:str):
		lin = line[:]
		lin = lin.upper().replace(' ', '')
		outsideComents = ""
		counter = 0
		for w in lin:
			if w == '(':
				counter += 1
			if counter == 0:
				outsideComents += w
			if w == ')':
				counter -= 1
		lin = outsideComents
		if lin.find('M47') != -1:
			self.repeatType = self.TYPE_M47
			if lin.find('P') != -1:
				self.repeatType = self.TYPE_M47P
			return True
		return 0
