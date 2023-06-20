import configparser
import os
import sys
from tkinter import Frame, Listbox
import tkinter
from tkinter.constants import BOTH, FALSE, LEFT, RIGHT, TRUE, TOP, VERTICAL, Y
from tkinter.ttk import Label, Scrollbar

fontSectionName = ("Helvetica", 16, 'bold')
fontOptionName = ("Helvetica", 14, 'bold')
fontOptionValue = ("Helvetica", 14)

config = configparser.ConfigParser()


def generateSection(master, sectionName, listview):
    listview.insert(listview.size(), sectionName)
    for option in config.options(sectionName):
        f3 = Frame()
        Label(f3, text=sectionName+"::"+option, font=fontOptionName).pack(side=LEFT)
        Label(f3, text=config.get(sectionName, option), font=fontOptionValue).pack(side=LEFT)
        f3.pack(side=TOP, fill=BOTH, expand=TRUE)
        listview.insert(listview.size(),f3)

def generateMain(master):
    frame = Frame(master)
    listview = Listbox(frame)
    listview.insert(1,"")
    scrollbar = Scrollbar(frame,orient=VERTICAL, command=listview.yview)
    scrollbar.pack(side=RIGHT,fill=Y,expand=TRUE)
    listview["yscrollcommand"] = scrollbar.set
    for section in config.sections():
        generateSection(frame, section, listview)
    frame.pack(side=TOP, expand=TRUE, fill=BOTH)

if __name__=="__main__":

    prgpath = os.path.abspath(os.path.dirname(sys.argv[0]))
    config.read(os.path.join(os.path.abspath(os.path.dirname(__file__)),"bCNC/bCNC.ini"))
    tk = tkinter.Tk()
    generateMain(tk)
    tk.mainloop()

