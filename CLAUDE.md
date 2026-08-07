# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

bCNC is a cross-platform (Windows/Linux/Mac) GRBL/grblHAL CNC g-code sender, autoleveler, g-code editor, digitizer and CAM tool, written in Python with a Tkinter GUI. This repo is a fork of `vlachoudis/bCNC` (tracked as the `upstream` remote); `origin` is `Erik-Morbach/bCNC`.

`bCNC/bCNC.py` is a **symlink** to `bCNC/__main__.py` (the ~2900-line monolithic application/GUI class) — they are the same file, so a fix applied to one is applied to both. Do not "sync" them. The `bCNC.py` at the *repo root* is a different, deliberately broken legacy loader that just prints "use instead: python -m bCNC".

## Deployment target

Production runs on a Raspberry Pi 4 (4 GB) with Debian Trixie and Python 3.11.2 built via pyenv; `rpi-cnc-4.sh` provisions it. The desktop launcher runs `$PYENV_ROOT/versions/3.11.2/bin/python bCNC` with the working directory set to the repo root — code that resolves paths relative to the current working directory therefore only works when launched that way. Prefer paths derived from `Utils.prgpath`.

## Running

    python -m bCNC          # run from repo root (git checkout) — always use this while developing
    pip install -e .        # editable install (used by CI before running from source)

There is no separate build step; this is a pure-Python Tkinter app.

## Tests

**The `tests/` suite is dead — do not try to run it or treat it as a regression gate.** Verified Aug 2026:

- `tests/static/sample.gcode` does not exist in the repo, so `test_can_load_and_run_sample_gcode` fails immediately on `shutil.copy`.
- The pinned dependencies are 2017-era and no longer installable on Python 3.11 (`pyautogui==0.9.36` fails at metadata build, `imageio==2.2.0` predates the `imageio.imread` removal).
- The `pytest` line is commented out in `.travis.yml` and has been for years; CI only ever ran `compileall` and `sdist`.
- `tests/base.py`'s `get_python_path()` returns `/usr/local/bin/python` unless `VIRTUAL_ENV` is set — wrong on the pyenv-based Pi.
- The harness drives the *real* screen and keyboard via `pyautogui`. Never run it on the Pi that is wired to the machine.

Reviving it is a project in itself. Until then, verify changes with targeted headless unit tests (stub `tkinter`/`CNC`/`Utils` via `sys.modules` to import a single module without a display), plus `python -tt -m compileall -f bCNC`, and then on real hardware.

For reference, the suite was full GUI smoke tests: launch the app as a subprocess, drive it with `pyautogui`, connect to a fake `gcode-receiver` GRBL server over a socket, assert against the pendant state endpoint (`http://127.0.0.1:5001/state`).

CI (`.travis.yml`) otherwise just does a compile check and sdist build:

    python -tt -m compileall -f bCNC
    python setup.py sdist

## Code architecture

**Module path setup**: `bCNC/bCNC.py`/`__main__.py` prepend `bCNC/lib`, `bCNC/plugins`, and `bCNC/controllers` to `sys.path` at import time, so modules within those directories import each other with flat (non-package) imports, e.g. `from CNC import CNC` rather than `from bCNC.CNC import CNC`.

**Core pieces (all in `bCNC/`):**
- `CNC.py` (largest file, ~4850 lines) — the g-code model: `CNC` (machine/work state, units, WCS), `GCode` (parsed program, blocks, block-based editing/optimization), `Block`. Nearly everything else depends on this.
- `Sender.py` — talks to the controller over serial (`Serial.py`) or a socket, manages the send/run state machine, queues g-code lines, tracks controller state (`STATECOLOR`/`NOT_CONNECTED`), owns `ProcessEngine`, `ProgramEngine`, `RepeatEngine`, `MacroEngine`, `ScriptEngine`, `Command` handling.
- `controllers/` — one class per firmware dialect (`GRBL0.py`, `GRBL1.py`, `SMOOTHIE.py`), all extending `_GenericController.py`/`_GenericGRBL.py`, translating generic Sender calls into controller-specific g-code/settings protocol.
- `CNCRibbon.py` / `Ribbon.py` / `Panel.py` — the ribbon-toolbar GUI framework; GUI "pages" (tabs) subclass `CNCRibbon.Page`.
- `EditorPage.py`, `ControlPage.py`, `ProbePage.py`, `FilePage.py`, `ToolsPage.py`, `TerminalPage.py` — the individual ribbon pages/tabs (g-code editor, jog/execution control, autolevel probing, file I/O, tool/material/plugin database, MDI terminal).
- `CNCCanvas.py` — the 2D/3D g-code/workspace canvas renderer.
- `Utils.py` — application-wide config (`bCNC.ini`, `~/.bCNC`), settings persistence, i18n helpers.
- `Pendant.py` + `pendant/` — the built-in web pendant (HTTP server for the phone/browser UI used by GUI tests to read run state).
- `Camera.py` — webcam-based work alignment/registration.
- `lib/` — vendored/support libraries: `dxf.py`, `svgcode.py`, `bstl.py`/`stl/` (STL import), `ply.py` (PLY mesh import), `meshcut.py` (mesh slicing), `bmath.py`/`bpath.py` (geometry), `tkExtra.py`/`tkDialogs.py`/`bFileDialog.py` (Tk widget helpers), `ttf.py`, `midiparser.py`, `rexx.py`, `undo.py`.

**Plugins (`bCNC/plugins/`)**: user-invokable g-code generators/transforms shown in the Tools page (box/bowl/gear/spirograph generators, drilling/trochoidal/tab-cutting CAM operations, etc.). Each plugin defines a class with a `__name__ = _("...")` translatable label and a set of typed parameters; they're registered/discovered via `ToolsPage.Plugin`. Follow an existing plugin (e.g. `box.py`) as the template for a new one — same param-declaration and `run()`/execute conventions, geometry via `bmath`/`CNC.Block`.

**Macros/scripts (`macros/`, `scripts/`)**: short standalone Python snippets end users can bind to M-codes or shortcut buttons; separate from the plugin system. `scripts/` lives at the **repo root**, not inside the `bCNC/` package, and is loaded by `ScriptEngine.loadScripts()` into a name→source dict keyed by the uppercased file stem (`UserHome.py` → `USERHOME`), then run with `exec()` via `Sender.executeCommand`.

Safety-critical: `UserHome` overrides the homing cycle with per-axis pull-off moves. If it is not loaded, `_GenericController.home()` falls back to plain `$H`, which applies the controller's single `$27` pull-off to *every* axis — physically dangerous. `loadScripts()` therefore skips directories and non-`.py` files (`__pycache__/`, editor backups like `UserHome.py~`, vim swap files, `.DS_Store`) and isolates each file read in its own `try/except`, so one bad entry cannot stop later scripts from loading. `home()` refuses to home when a `UserHome` script exists on disk but failed to load, rather than silently using `$27`. Keep both of those properties intact.

## Conventions in this codebase

- Mixed Python 2/3 support is still present in older files (`from __future__ import ...`, `try/except` import fallbacks for `Tkinter`/`tkinter`) — PRs are expected to work on both python2 and python3 per `README.md`, though newer code targets Python 3 (`setup.py`/`opencv` version pinning branches on `sys.version_info`).
- Translatable strings use `_()` (set up by `Utils` config loading before other imports).
- User-facing config defaults live in `bCNC/bCNC.ini`; do not edit it as a way of storing user preferences — per-user overrides go to `~/.bCNC`.
- The GRBL controller should be configured with `$10=3` (MPos) and `$13=0` (mm) — relevant when writing code that reads/parses controller position/state.
