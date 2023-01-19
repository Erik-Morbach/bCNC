import types
import Utils
import Command
from CNC import CNC

class ProcessNode:
	def __init__(self) -> None:
		self.shouldWait = 0
		self.cmd = ""
		self.app = None

	def shouldEvaluateHere(self, cmd) -> bool:
		pass

	def preprocessCommand(self, cmd):
		self.cmd = cmd

	def process(self) -> list[Command.Command]:
		pass


class ProcessEngine:
	def __init__(self, app) -> None:
		self.nodes = []
		self.app = app
		self.registerProcessNode(EvaluateNode())
		self.registerProcessNode(CannedCycleNode())
		self.registerProcessNode(MacroNode())

	def getValidProcessNode(self, cmd) -> ProcessNode|None:
		nodesCp = self.nodes[:]
		for node in nodesCp:
			if node.shouldEvaluateHere(cmd):
				return node
		return None

	def registerProcessNode(self, pNode):
		self.nodes += [pNode]
		self.nodes[-1].app = self.app


class EvaluateNode(ProcessNode):
	def __init__(self) -> None:
		super().__init__()

	def shouldEvaluateHere(self, cmd) -> bool:
		if isinstance(cmd.src, list): return True
		if isinstance(cmd.src, types.CodeType): return True
		return False

	def process(self) -> list[Command.Command]:
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
			self.app._gcount += 1
		return response;


class CannedCycleNode(ProcessNode):
	def __init__(self) -> None:
		super().__init__()
		self.shouldWait = 1
		self.cycles = {}
		self.cycles[83] = self.g83

	def g83(self, cmd):
		lines = []

		z = CNC.vars['wz']

		clearz = max(cmd.args['R'], z)
		drill   = cmd.args['Z']
		retract = cmd.args['R']

		peck = cmd.args['Q']
		feed = cmd.args['F']

		lineNumberCode = ""
		if 'N' in cmd.rawArgs.keys():
			lineNumberCode = 'N'+cmd.rawArgs['N']


		lines.append(lineNumberCode + CNC.grapid(z=retract))
		z = retract

		if 'X' in cmd.args.keys():
			lines.append(lineNumberCode + CNC.grapid(x=cmd.args['X']))

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

	def shouldEvaluateHere(self, cmd) -> bool:
		if 'G' not in cmd.args.keys(): return False
		return int(cmd.args['G']) in self.cycles.keys()

	def process(self) -> list[Command.Command]:
		return self.cycles[int(self.cmd.args['G'])](self.cmd)

class MacroNode(ProcessNode):
	def __init__(self) -> None:
		super().__init__()
		self.shouldWait = 1

	def shouldEvaluateHere(self, cmd) -> bool:
		if 'M' not in cmd.args.keys(): return False
		mcode = int(cmd.args['M'])
		return Utils.macroExists(mcode)

	def process(self) -> list[Command.Command]:
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
