if get('jogOldStep') == -1:
    set('jogOldStep', self.control.step.get())
self.control.step.set(0.01)
