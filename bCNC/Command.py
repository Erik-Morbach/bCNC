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
				args[currentName] += c
				stage = 1
		return args


def cmdFactory(cmd):
	if isinstance(cmd, Command): return cmd
	return Command(cmd)

