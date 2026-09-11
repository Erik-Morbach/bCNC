#!/usr/bin/env python3
"""Headless regression tests for the MPG plumbing.

The tests/ suite proper is dead and drives the real screen with pyautogui --
see CLAUDE.md, and never run it on the Pi wired to the machine. These tests
are the opposite: they stub tkinter, CNC and the Pi-only modules through
sys.modules so single modules can be imported and exercised with no display,
no hardware and no controller.

    python3 tests/headless/test_mpg.py
"""
import io
import os
import sys
import time
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, os.pardir, os.pardir))
PKG = os.path.join(ROOT, "bCNC")
for _p in (PKG, os.path.join(PKG, "lib"), os.path.join(PKG, "controllers")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

FAILURES = []


def check(name, condition, detail=""):
    if condition:
        print("  ok   %s" % name)
    else:
        print("  FAIL %s %s" % (name, detail))
        FAILURES.append(name)


# ---------------------------------------------------------------- stubs
class _EventType:
    KeyPress = 2


def _dummy_class(name):
    """A widget-shaped placeholder: constructible, subclassable, inert."""
    return type(name, (object,), {
        "__init__": lambda self, *a, **k: None,
        "__getattr__": lambda self, n: (lambda *a, **k: None),
    })


_TK_CONSTANTS = {
    "TRUE": 1, "FALSE": 0, "YES": 1, "NO": 0, "ON": 1, "OFF": 0,
}
for _name in ("LEFT RIGHT TOP BOTTOM X Y BOTH NONE W E N S NW NE SW SE EW NS "
              "NSEW NSW NEW CENTER HORIZONTAL VERTICAL NORMAL DISABLED ACTIVE "
              "HIDDEN END INSERT ANCHOR SEL SEL_FIRST SEL_LAST FLAT RAISED "
              "SUNKEN GROOVE RIDGE SOLID SINGLE BROWSE MULTIPLE EXTENDED "
              "MOVETO SCROLL UNITS PAGES ALL CURRENT BUTT PROJECTING ROUND "
              "BEVEL MITER LAST FIRST NUMERIC CHAR WORD BASELINE INSIDE "
              "OUTSIDE ARC CHORD PIESLICE READABLE WRITABLE EXCEPTION").split():
    _TK_CONSTANTS.setdefault(_name, _name.lower())

_TK_CLASSES = ("Tk Toplevel Frame Label Entry Button Checkbutton Radiobutton "
               "Canvas Listbox Menu Menubutton Message Scale Scrollbar Text "
               "Spinbox LabelFrame PanedWindow OptionMenu Widget BaseWidget "
               "Misc Variable StringVar IntVar DoubleVar BooleanVar "
               "PhotoImage BitmapImage Image Event Grid Pack Place Wm "
               "Canvas Menubutton").split()


class _TkModule(types.ModuleType):
    """Fabricates any tkinter name on demand so star-imports resolve."""

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        if name.isupper():
            value = _TK_CONSTANTS.get(name, name.lower())
        else:
            value = _dummy_class(name)
        setattr(self, name, value)
        return value


_tk = _TkModule("tkinter")
_tk.__path__ = []                       # let "import tkinter.font" resolve
_tk.EventType = _EventType
_tk.TclError = type("TclError", (Exception,), {})
_tk.__all__ = _TK_CLASSES + sorted(_TK_CONSTANTS) + ["TclError", "EventType"]
sys.modules["tkinter"] = _tk
for _sub in ("font", "messagebox", "colorchooser", "filedialog",
             "simpledialog", "scrolledtext", "commondialog", "dialog", "ttk",
             "constants"):
    _mod = _TkModule("tkinter." + _sub)
    setattr(_tk, _sub, _mod)
    sys.modules["tkinter." + _sub] = _mod
sys.modules["mttkinter"] = types.ModuleType("mttkinter")

_gpio = types.ModuleType("gpiozero")


class _Button:
    def __init__(self, pin, pull_up=False):
        self.is_pressed = False


_gpio.Button = _Button
sys.modules.setdefault("gpiozero", _gpio)

# Controllable fake I2C bus.
BUS_BEHAVIOUR = {"mode": "ok", "value": 0}


class _SMBus:
    def __init__(self, n):
        if BUS_BEHAVIOUR["mode"] == "nobus":
            raise IOError("no bus")

    def read_byte_data(self, dev, addr):
        if BUS_BEHAVIOUR["mode"] == "fail":
            raise IOError("read failed")
        return BUS_BEHAVIOUR["value"]


_smbus = types.ModuleType("smbus2")
_smbus.SMBus = _SMBus
sys.modules.setdefault("smbus2", _smbus)

# Minimal CNC stand-in: only the shared variable dict is needed here.
_cncmod = types.ModuleType("CNC")


class _CNC:
    vars = {
        "inputs": 0,
        "state": "Idle",
        "planner": -1,
        "JogActive": True,
        "mpgAxis": "",
        "mpgScale": 0.0,
        "panelFault": False,
    }


_cncmod.CNC = _CNC
sys.modules["CNC"] = _cncmod


# ------------------------------------------------------- Panel resilience
def test_panel():
    print("Panel: I2C faults must not kill the member thread")
    import Panel

    bus = Panel.i2c()
    bus.setup(0x20, 0x00, -1)

    BUS_BEHAVIOUR["mode"] = "fail"
    try:
        value = bus.read(0x20, 0x00)
        raised = None
    except BaseException as exc:          # noqa: BLE001 - that is the point
        value, raised = None, exc
    check("read survives total I2C failure", raised is None,
          "raised %r (this was an UnboundLocalError before)" % (raised,))
    check("read holds the last known value", value == 0, "got %r" % (value,))
    check("read flags the fault", bus.fault is True)

    BUS_BEHAVIOUR["mode"] = "ok"
    BUS_BEHAVIOUR["value"] = 7
    check("read recovers", bus.read(0x20, 0x00) == 7)
    check("fault clears on recovery", bus.fault is False)

    # A bus that never opened must degrade, not explode.
    BUS_BEHAVIOUR["mode"] = "nobus"
    dead = Panel.i2c()
    check("missing bus is recorded", dead.bus is None and dead.fault is True)
    dead.setup(0x20, 0x00, -1)
    try:
        dead.read(0x20, 0x00)
        raised = None
    except BaseException as exc:          # noqa: BLE001
        raised = exc
    check("read on a missing bus does not raise", raised is None,
          "raised %r" % (raised,))
    BUS_BEHAVIOUR["mode"] = "ok"

    # A raising pin read must not end the polling thread.
    _CNC.vars["panelFault"] = False
    member = Panel.Member()
    member.setup(["e0"], 0, 0.02, lambda values: None, True)

    original = Panel.PINS.read

    def exploding(pin):
        raise RuntimeError("boom")

    Panel.PINS.read = exploding
    try:
        member.start()
        time.sleep(0.3)
        check("member thread is still alive", member.th.is_alive())
        check("errors are counted", member.errorCount > 0,
              "errorCount=%d" % member.errorCount)
        check("fault is visible in CNC.vars", _CNC.vars["panelFault"] is True)
    finally:
        Panel.PINS.read = original
        member.stop()
        time.sleep(0.1)


# ----------------------------------------------------- JogController gating
class _FakeVar:
    def __init__(self, value):
        self.val = value
        self.value = value


class _FakeApp:
    def __init__(self):
        self.running = _FakeVar(False)
        self.events = []

    def bind(self, *args, **kwargs):
        pass

    def event_generate(self, name, **kwargs):
        self.events.append(name)

    def acceptKey(self):
        return True


def test_jog_gating():
    print("JogController: the watchdog must not cancel other people's jogs")
    import JogController as JCmod

    cwd = os.getcwd()
    os.chdir(ROOT)                      # jogConf.txt is read relative to cwd
    try:
        app = _FakeApp()
        jc = JCmod.JogController(app, {})
        jc.stopTask()                   # stop the background thread
        time.sleep(0.2)
    finally:
        os.chdir(cwd)

    def run(mpg_axis, owned, state, age=None):
        """age: seconds since bCNC last issued a jog of its own."""
        if age is None:
            age = jc.period * 1.5       # stale enough to trip the watchdog
        _CNC.vars["mpgAxis"] = mpg_axis
        _CNC.vars["state"] = state
        jc.owned = owned
        jc.lastTime.value = time.time() - age
        app.events = []
        jc.update()
        return app.events

    check("legacy behaviour unchanged when MPG is off",
          "<<JogStop>>" in run("", False, "Jog"))
    check("firmware MPG jog is left alone",
          run("X", False, "Jog") == [],
          "watchdog fired on a jog bCNC did not start")
    check("bCNC's own jog still gets stopped with MPG on",
          "<<JogStop>>" in run("X", True, "Jog"))

    # A stuck ownership flag would lock the handwheel out for the rest of the
    # session, so it has to expire on its own.
    events = run("X", True, "Jog", age=jc.ownTimeout + 1.0)
    check("stale ownership expires", jc.owned is False)
    check("wheel is free again once ownership expired", events == [])


# ------------------------------------------------- ControlPage init order
def test_controlpage_guards():
    """tkExtra.Combobox.set() invokes the widget command immediately.

    ControlFrame builds the step combobox before the MPG widgets exist, so a
    callback firing early would raise straight out of Application.__init__ and
    bCNC would not start at all. Importing ControlPage headlessly drags in the
    whole GUI stack, so this checks the invariant at source level instead.
    """
    print("ControlPage: MPG callbacks must be safe before the frame is built")
    src = io.open(os.path.join(PKG, "ControlPage.py"), encoding="utf-8").read()

    flag = src.find("self._mpgReady = False")
    first_combobox = src.find("tkExtra.Combobox(")
    check("the ready flag is set before any combobox is built",
          0 <= flag < first_combobox,
          "flag at %d, first combobox at %d" % (flag, first_combobox))

    for name in ("mpgAxisChanged", "stepChanged", "updateMpgStatus", "mpgOff"):
        start = src.find("    def %s(self" % name)
        end = src.find("\n    def ", start + 1)
        body = src[start:end if end > 0 else len(src)]
        check("%s() checks the ready flag" % name, "_mpgReady" in body)


if __name__ == "__main__":
    import io  # noqa: F401 - used by test_controlpage_guards
    test_panel()
    test_jog_gating()
    test_controlpage_guards()
    print()
    if FAILURES:
        print("%d FAILED: %s" % (len(FAILURES), ", ".join(FAILURES)))
        sys.exit(1)
    print("all headless MPG tests passed")
