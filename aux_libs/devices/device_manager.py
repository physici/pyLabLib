from ...core.fileio import loadfile  #@UnresolvedImport

import importlib
import re
import os.path

class DeviceManager(object):
    def __init__(self, path=None):
        object.__init__(self)
        self.devices={}
        self.opened={}
        if path:
            self.add_from_file(path)
        
    def add_device(self, name, dev_cls, addr):
        if not (isinstance(addr,tuple) or isinstance(addr,dict)):
            addr=(addr,)
        self.devices[name]=(dev_cls,addr)
    @staticmethod
    def _get_class(name):
        mdln,clsn=name.rsplit(".")
        mdl=importlib.import_module(".."+mdln,__name__)
        cls=getattr(mdl,clsn)
        return cls
    def add_from_file(self, path):
        descr=loadfile.load(path,"csv",dtype="generic",columns=["name","class","address"])
        for name,cls,addr in descr.r:
            name=re.sub(r"\s+","_",name)
            self.add_device(name,self._get_class(cls),addr)
                
    def get_device(self, name, reopen=False):
        if (not reopen) and (name in self.opened):
            return self.opened[name]
        dev_cls,addr=self.devices[name]
        if isinstance(addr,dict):
            dev=dev_cls(**addr)
        else:
            dev=dev_cls(*addr)
        self.opened[name]=dev
        return dev
    __getitem__=get_device
    __getattr__=get_device
    def __dir__(self):
        return self.devices.keys()
    
    
def default_device_manager(name="devices.txt"):
    desktop_path=os.path.expanduser("~/Desktop")
    return DeviceManager(os.path.join(desktop_path,name))

try:
    mgr=default_device_manager()
except IOError:
    pass