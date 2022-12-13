workBoard = 1
swapBoard = 2
wait()
code('$500=0'); wait()
code('G53 G0 X[xWork]'); wait()
code('$500=%d' % workBoard); wait()
code('G53 G0 X[xTroca]'); wait()
code('$500=%d' % swapBoard); wait()
code('G53 G0 X[xWork]'); wait()
code('$500=%d' % swapBoard); wait()
