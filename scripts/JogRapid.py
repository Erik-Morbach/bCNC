if get("jog_old_step") == -1:
    set("jog_old_step", self.control.step.get())
self.control.step.set(100)
