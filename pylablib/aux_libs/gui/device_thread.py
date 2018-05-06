from ...core.gui.qt.thread import controller, threadprop
from ...core.utils import general, py3, dictionary

from PyQt4 import QtCore
class DeviceThread(controller.QTaskThread):
    def __init__(self, name=None, devargs=None, devkwargs=None, signal_pool=None):
        controller.QTaskThread.__init__(self,name=name,signal_pool=signal_pool,setupargs=devargs,setupkwargs=devkwargs)
        self.device=None
        
    def finalize_task(self):
        if self.device is not None:
            self.device.close()

    def update_status(self, kind, status, text=None, notify=True):
        status_str="status/"+kind if kind else "status"
        self[status_str]=status
        if notify:
            self.send_signal("any",status_str+"/"+status)
        if text:
            self.set_variable(status_str+"_text",text)
            self.send_signal("any",status_str+"_text",text)