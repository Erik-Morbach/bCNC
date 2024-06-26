import types
import Utils
import Command
from CNC import CNC

class ProcessNode:
	def __init__(self):
		self.shouldWait = 0
		self.cmd = ""
		self.app = None
		self.name = "Null"

	def shouldEvaluateHere(self, cmd):
		pass

	def preprocessCommand(self, cmd):
		self.cmd = cmd

	def process(self):
		pass

	def __str__(self):
		return self.name


class ProcessEngine:
	def __init__(self, app):
		self.nodes = []
		self.app = app
		self.registerProcessNode(EvaluateNode())
		self.registerProcessNode(CannedCycleNode())
		self.registerProcessNode(MacroNode())

	def getValidProcessNode(self, cmd):
		nodesCp = self.nodes[:]
		for node in nodesCp:
			if node.shouldEvaluateHere(cmd):
				return node
		return None

	def registerProcessNode(self, pNode):
		self.nodes += [pNode]
		self.nodes[-1].app = self.app


class EvaluateNode(ProcessNode):
	def __init__(self):
		super().__init__()
		self.name = "Evaluate"

	def shouldEvaluateHere(self, cmd):
		if isinstance(cmd.src, list): return True
		if isinstance(cmd.src, types.CodeType): return True
		return False

	def process(self):
		line = ""
		response = []
		try:
			line = self.app.gcode.evaluate(self.cmd.src)
		except Exception as err:
			print(err)
			self._stop = True
			return []
		if isinstance(line, str):
			line += "\n"
			response += [Command.Command(line)]
		else:
			self.app._gcount.assign(lambda x: x + 1)
		return response;


class CannedCycleNode(ProcessNode):
	def __init__(self):
		super().__init__()
		self.shouldWait = 1
		self.cycles = {}
#		self.cycles[83] = self.g83 # Is already implemented correct on Esp32
		self.name = "Canned Cycles"


	def g83(self, cmd):
		lines = []

		z = CNC.vars['wz']

		clearz = max(cmd.args['R'], z)
		drill   = cmd.args['Z']
		retract = cmd.args['R']

		peck = cmd.args['Q']
		feed = CNC.vars["feed"]
		if 'F' in cmd.args.keys():
			feed = cmd.args['F']

		if peck < 0:
			peck = abs(peck)

		lineNumberCode = ""
		if 'N' in cmd.rawArgs.keys():
			lineNumberCode = 'N'+cmd.rawArgs['N']


		lines.append(lineNumberCode + CNC.grapid(z=retract))
		z = retract

		if 'X' in cmd.args.keys():
			lines.append(lineNumberCode + CNC.grapid(x=cmd.args['X']))

		if 'Y' in cmd.args.keys():
			lines.append(lineNumberCode + CNC.grapid(y=cmd.args['Y']))

		# Rapid move parallel to retract
		currentZ = z

		while currentZ > drill:
			if currentZ != retract:
				lines.append(lineNumberCode + CNC.grapid(z=retract))
			
			lines.append(lineNumberCode + CNC.grapid(z=(2+currentZ))) #rapid to aproximate
			currentZ = max(drill, currentZ-peck)
			# Drill to z
			lines.append(lineNumberCode + CNC.gline(z=currentZ,f=feed))
		z = clearz
		lines.append(lineNumberCode + CNC.grapid(z=z))
		lines = [w+'\n' for w in lines]
		return lines

	def shouldEvaluateHere(self, cmd):
		if 'G' not in cmd.args.keys(): return False
		return int(cmd.args['G']) in self.cycles.keys()

	def process(self):
		return self.cycles[int(self.cmd.args['G'])](self.cmd)

class MacroNode(ProcessNode):
	def __init__(self):
		super().__init__()
		self.shouldWait = 1
		self.name = "Macro"

	def shouldEvaluateHere(self, cmd):
		if 'M' not in cmd.args.keys(): return False
		mcode = int(cmd.args['M'])
		return Utils.macroExists(mcode)

	def process(self):
		mcode = int(self.cmd.args['M'])
		executor = Utils.macroExecutor(mcode, self.app, CNC)
		try:
			executor.execute(CNC.vars, self.app.gcode.vars)
		except Exception as err:
			print(err)
			return []
		queue = executor.getQueue()
		vec = []
		while not queue.empty():
			vec += [queue.get()]
		return vec
