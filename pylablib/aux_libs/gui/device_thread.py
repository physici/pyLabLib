from ...core.gui.qt.thread import controller

class DeviceThread(controller.QTaskThread):
    def __init__(self, name=None, devargs=None, devkwargs=None, signal_pool=None):
        controller.QTaskThread.__init__(self,name=name,signal_pool=signal_pool,setupargs=devargs,setupkwargs=devkwargs)
        self.device=None
        self.add_command("open_device",self.open_device)
        self.add_command("close_device",self.close_device)
        
    def finalize_task(self):
        self.close_device()

    def open_device(self):
        if self.device is not None:
            self.device.open()
            self.update_status("connection","opened","Connected")
    def close_device(self):
        if self.device is not None:
            self.device.close()
            self.update_status("connection","closed","Disconnected")

    def update_status(self, kind, status, text=None, notify=True):
        status_str="status/"+kind if kind else "status"
        self[status_str]=status
        if notify:
            self.send_signal("any",status_str+"/"+status)
        if text:
            self.set_variable(status_str+"_text",text)
            self.send_signal("any",status_str+"_text",text)