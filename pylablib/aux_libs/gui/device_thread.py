from ...core.gui.qt.thread import controller
from ...core.utils import rpyc as rpyc_utils

class DeviceThread(controller.QTaskThread):
    def __init__(self, name=None, devargs=None, devkwargs=None, signal_pool=None):
        controller.QTaskThread.__init__(self,name=name,signal_pool=signal_pool,setupargs=devargs,setupkwargs=devkwargs)
        self.device=None
        self.add_command("open_device",self.open_device)
        self.add_command("close_device",self.close_device)
        self.add_command("get_settings",self.get_settings)
        self.add_command("get_full_info",self.get_full_info)
        self._full_info_job=False
        self._full_info_nodes=None
        self.rpyc=False
        
    def finalize_task(self):
        self.close_device()

    def rpyc_device(self, remote, module, device, *args, **kwargs):
        self.rpyc=True
        self.rpyc_serv=rpyc_utils.connect_device_service(remote)
        if not self.rpyc_serv:
            return None
        return self.rpyc_serv.get_device(module,device,*args,**kwargs)
    def rpyc_obtain(self, obj):
        if self.rpyc:
            return rpyc_utils.obtain(obj,serv=self.rpyc_serv)
        return obj

    def connect_device(self):
        pass
    def open_device(self):
        if self.device is not None and self.device.is_opened():
            return True
        self.update_status("connection","opening","Connecting...")
        if self.device is None:
            self.connect_device()
        if self.device is not None:
            if not self.device.is_opened():
                self.device.open()
            if self.device.is_opened():
                self.update_status("connection","opened","Connected")
                return True
        self.update_status("connection","closed","Disconnected")
        return False
    def close_device(self):
        if self.device is not None and self.device.is_opened():
            self.update_status("connection","closing","Disconnecting...")
            self.device.close()
            self.update_status("connection","closed","Disconnected")

    def update_status(self, kind, status, text=None, notify=True):
        status_str="status/"+kind if kind else "status"
        self[status_str]=status
        if notify:
            self.send_signal("any",status_str,status)
        if text:
            self.set_variable(status_str+"_text",text)
            self.send_signal("any",status_str+"_text",text)

    def get_settings(self):
        return self.rpyc_obtain(self.device.get_settings()) if self.device is not None else {}
    
    def setup_full_info_job(self, period=2., nodes=None):
        if not self._full_info_job:
            self._full_info_nodes=nodes
            self.add_job("update_full_info",self.update_full_info,period)
            self._full_info_job=True
    def update_full_info(self):
        self["full_info"]=self.rpyc_obtain(self.device.get_full_info(nodes=self._full_info_nodes))
    def get_full_info(self):
        if self.device:
            return self["full_info"] if self._full_info_job else self.rpyc_obtain(self.device.get_full_info(nodes=self._full_info_nodes))
        else:
            return {}