from CNC import CNC
class Command:
	def __init__(self, cmd):
		self.src = cmd
		self.isJog = False
		self.rawArgs = self.extractRawArgs()
		self.args = {}
		for (a,b) in self.rawArgs.items():
			try: #TODO: remove this shit
				self.args[a] = float(b)
			except:
				pass

	def processFuture(self):
		if 'G' not in self.rawArgs.keys(): return
		inc = 'G91' in self.rawArgs['G']
		for w in "XYZABC":
			value = CNC.vars["w{}".format(w.lower())]
			if inc:
				value += self.args[w]
			else:
				value = self.args[w]
			CNC.vars["fw{}".format(w.lower())] = value


	def checkLimitsValid(self, app):
		p0 = 456 if CNC.vars["port0State"] else 123
		p1 = 101112 if CNC.vars["port1State"] else 789
		table = app.limitTable
		minLimits, maxLimits = table.getRow(-p0)[0],\
								table.getRow(p0)[0]

		minLimits2, maxLimits2 = table.getRow(-p1)[0],\
								table.getRow(p1)[0]

		for w in "abc":
			minLimits[w] = minLimits2[w]
			maxLimits[w] = maxLimits2[w]
		for w in "xyzabc":
			minLimits[w] = float(minLimits[w])
			maxLimits[w] = float(maxLimits[w])
		values = self.args
		axis = "XYZABC"
		for w in axis:
			if w not in values.keys():
				values[w] = 0
		if self.isJog:
			for w in axis:
				values[w] = values[w] + CNC.vars["fw{}".format(w.lower())]
		for axe in axis:
			currentValue = values[axe]
			axe = axe.lower()
			if not (minLimits[axe] <= currentValue and currentValue <= maxLimits[axe]):
				return False
		return True


	def extractRawArgs(self):
		if not isinstance(self.src, str): return {}

		cmd = self.src.upper().replace(' ','')
		if cmd.startswith("$J="):
			cmd = cmd[3:]
			self.isJog = True
		args = {}
		commentCount = 0
		currentName = "" # stage 0

		stage = 0
		for c in cmd:
			if c=='(': 
				stage = 1
				commentCount += 1
				continue
			if c==')':
				stage = 1
				commentCount -= 1
				continue

			if commentCount != 0: continue
			if c.isalpha():
				if stage != 0:
					currentName = ""
				currentName += c
				stage = 0
				continue
			if c.isdigit() or c in ".-+":
				if currentName not in args.keys():
					args[currentName] = ""
				if stage==0:
					if len(args[currentName]) != 0:
						args[currentName] += ','
				args[currentName] += c
				stage = 1
		return args


def cmdFactory(cmd):
	if isinstance(cmd, Command): return cmd
	return Command(cmd)

