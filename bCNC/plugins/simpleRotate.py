# Author:	DodoLaSaumure
# Date:	30-Dec-2019

from __future__ import absolute_import
from __future__ import print_function
__author__ = "DodoLaSaumure"
__email__  = ""


import math
from bmath import Vector
from CNC import CW,CNC,Block
from ToolsPage import Plugin
from CNCRibbon    import Page
try:
# 	import Tkinter
# 	from Tkinter import *
	import tkMessageBox
except ImportError:
# 	import tkinter
# 	from tkinter import *
	import tkinter.messagebox as tkMessageBox


#==============================================================================
# Create a simple Rotate
#==============================================================================
class Tool(Plugin):
	__doc__ = _("Rotates a block to a new position")

	def __init__(self, master):
		Plugin.__init__(self, master, "SimpleRotate")
		self.icon  = "SimpleRotate"
		self.group = "Generator"
		self.variables = [
			("xcenter",        "float",    10.0, _("x center")),
			("ycenter",        "float",    10.0, _("y center")),
			("alpha",        "float",    90.0, _("angle step (degrees)")),
			("nbrepeat",        "int",    2, _("nb repeat including original")),
			("keep",        "bool",    True, _("Keep original yes/no")),
		]
		self.buttons.append("exe")

	# ----------------------------------------------------------------------
	def execute(self, app):
		n = self["name"]
		xcenter = self["xcenter"]
		ycenter = self["ycenter"]
		alpha = self["alpha"]
		nbrepeat = self["nbrepeat"]
		if nbrepeat ==1 :
			nbrepeat =2
		keep = self["keep"]
		blocks = app.editor.getSelectedBlocks()
		if not blocks:
			app.editor.selectAll()
			blocks = app.editor.getSelectedBlocks()
		if not blocks:
			tkMessageBox.showerror(_("Tile error"),
				_("No g-code blocks selected"))
			return
		pos = blocks[-1]	# insert position
		alpha_current = alpha
		pos += 1
		for index in range(int(nbrepeat-1)):
			# clone selected blocks
			undoinfo = []
			newblocks = []
			for bid in blocks:
				undoinfo.append(app.gcode.cloneBlockUndo(bid, pos))
				newblocks.append((pos,None))
				pos += 1
			app.addUndo(undoinfo)
			app.gcode.rotateLines(newblocks,alpha_current, xcenter, ycenter)
			alpha_current+=alpha
		if not keep :
			app.editor.deleteBlock()
		app.refresh()
		app.setStatus(_("Rotated selected blocks"))

if __name__=="__main__":
	pass
