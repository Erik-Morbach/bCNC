workBoard = 1
swapBoard = 2
setSettings(500,0)
code('G53 G0 X[xWork]'); wait()
setSettings(500,workBoard)
code('G53 G0 X[xTroca]'); wait()
setSettings(500,swapBoard)
code('G53 G0 X[xWork]'); wait()
