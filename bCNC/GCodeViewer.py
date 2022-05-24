import tkinter as tk
from tkinter import ttk
from CNC import CNC

import tkExtra

class GCodeViewer:
    def __init__(self, frame, app, *args, **kwargs):
        self.lb = tk.Listbox(frame,
                             selectmode = tk.SINGLE,
                             background = tkExtra.GLOBAL_CONTROL_BACKGROUND,
                             selectbackground = "gray",
                             *args,
                             **kwargs)

        sb = tk.Scrollbar(frame, orient=tk.VERTICAL, command=self.lb.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.lb.config(yscrollcommand=sb.set)
        self.app = app

    def pack(self, *args, **kwargs):
        self.lb.pack(*args, **kwargs)

    def update(self):
        lineNumber = max(0, CNC.vars["line"]-1)
        if self.app.running:
            self.lb.activate(lineNumber)
            self.lb.see(lineNumber)
        for w in self.lb.curselection():
            self.lb.selection_clear(w)
        self.lb.selection_set(lineNumber)


    def reload(self):
        self.lb.delete(0, self.lb.size()-1)
        blocks = self.app.gcode.blocks
        index = 0
        for block in blocks:
            for line in block:
                self.lb.insert(index, line)
                index+=1
