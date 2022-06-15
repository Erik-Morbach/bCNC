from CNCRibbon    import Page
#==============================================================================
# BJM Repeat Commands Class 
#==============================================================================
class RepeatEngine:
	TYPE_NONE = 0
	TYPE_M47 = 1
	TYPE_M47P = 2
	TIMEOUT_TO_REPEAT = 0.5
	repeatType: int
	m30CounterLimit: int
	m30Counter: int
	app: any
	fromSD: bool
	def __init__(self, CNCRef):
		self.cleanState()
		self.CNCRef = CNCRef

	def isRepeatable(self):
		if self.CNCRef.vars["barEnd"] == 0:
			return False
		if self.repeatType == self.TYPE_M47:
			return True
		self.updateState()
		if self.repeatType == self.TYPE_M47P and self.m30CounterLimit > self.m30Counter:
			return True
		return False

	def countRepetition(self):
		self.m30Counter += 1
		self.updateState()
	
	def updateState(self):
		try:
			if not self.fromSD:
				self.m30CounterLimit = self.CNCRef.vars["M30CounterLimit"]
			Page.groups["Run"].setM30Counter(self.m30Counter)
		except:
			pass
	
	def cleanState(self):
		self.m30Counter = 0
		self.m30CounterLimit = 0
		self.repeatType = self.TYPE_NONE
		self.fromSD = False
		self.updateState()

	def isRepeatCommand(self, line:str):
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
				self.m30CounterLimit = int(lin[lin.find('P') + 1:])
				Page.groups["Run"].setM30CounterLimit(self.m30CounterLimit)
				self.CNCRef.vars["M30CounterLimit"] = self.m30CounterLimit
			return True and not self.fromSD
		return 0
