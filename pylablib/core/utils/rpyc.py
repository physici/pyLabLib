"""Routines and classes related to RPyC package"""

from . import module as module_utils

import numpy as np
import rpyc

import importlib



_numpy_block_size=int(2**22)

def obtain(proxy):
    """
    Obtain a remote netfref object by value (i.e., copy it to the local Python instance).

    Wrapper around :func:`rpyc.classic.obtain` with some special cases handling.
    """
    if not isinstance(proxy,rpyc.BaseNetref):
        return proxy
    if isinstance(proxy, np.ndarray):
        elsize=np.prod(proxy.shape,dtype="u8")
        bytesize=proxy.dtype.itemsize*elsize
        if bytesize>_numpy_block_size:
            fproxy=proxy.flatten()
            loc=np.zeros(elsize,dtype=proxy.dtype.str)
            block_size=_numpy_block_size//proxy.dtype.itemsize
            for pos in range(0,elsize,block_size):
                loc[pos:pos+block_size]=rpyc.classic.obtain(fproxy[pos:pos+block_size])
            return loc.reshape(proxy.shape)
    return rpyc.classic.obtain(proxy)



class DeviceService(rpyc.SlaveService):
    """
    Device RPyC service.

    Expands on :class:`rpyc.SlaveService` by adding :meth:`get_device` method,
    which tracks opened devices and closes them automatically on disconnect.
    """
    def on_connect(self, conn):
        rpyc.SlaveService.on_connect(self,conn)
        self.devices=[]
    def on_disconnect(self, conn):
        for dev in self.devices:
            try:
                dev.close()
            except:
                pass
        self.devices=[]
        rpyc.SlaveService.on_disconnect(self,conn)
    def get_device(self, module, cls, *args, **kwargs):
        """
        Connect to a device.

        `cls` and `module` are names of the device class and the containing module
        (for module name the ``"pylablib.aux_libs.devices"`` prefix can be omitted)
        """
        try:
            module=importlib.import_module(module)
        except ModuleNotFoundError:
            module=importlib.import_module(module_utils.get_library_name()+".aux_libs.devices."+module)
        module._rpyc=True
        cls=module.__dict__[cls]
        dev=cls(*args,**kwargs)
        self.devices.append(dev)
        return dev

def run_device_service(port=18812):
    """Start :class:`DeviceService` at the given port"""
    rpyc.ThreadedServer(DeviceService,port=port).start()