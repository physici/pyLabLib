from ...core.gui.qt import thread

from PyQt4 import QtCore

import threading

class DeviceThread(thread.QMultiRepeatingThreadController):
    def __init__(self, name=None, devargs=None, devkwargs=None, signal_pool=None):
        thread.QMultiRepeatingThreadController.__init__(self,name=name)
        self.devargs=devargs or []
        self.devkwargs=devkwargs or {}
        self.device=None
        self._signal_pool=signal_pool
        self._signal_pool_uids=[]
        self._cached_var={}
        self._cached_var_lock=threading.Lock()
        self._directed_signal.connect(self._on_directed_signal)
        self.c=self.CommandAccess(self,sync=False)
        self.q=self.CommandAccess(self,sync=True)

    def setup_device(self, *args, **kwargs):
        pass
    def process_signal(self, src, tag, value):
        pass
    def process_command(self, *args, **kwargs):
        pass
    def process_query(self, *args, **kwargs):
        pass
    def close_device(self):
        if self.device is not None:
            self.device.close()

    def on_start(self):
        self.setup_device(*self.devargs,**self.devkwargs)
        if self._signal_pool:
            uid=self._signal_pool.subscribe_nonsync(self._recv_directed_signal,dsts=self.name)
            self._signal_pool_uids.append(uid)
    def on_finish(self):
        self.close_device()
        for uid in self._signal_pool_uids:
            self._signal_pool.unsubscribe(uid)

    _directed_signal=QtCore.pyqtSignal("PyQt_PyObject")
    @QtCore.pyqtSlot("PyQt_PyObject")
    def _on_directed_signal(self, msg):
        self.process_signal(*msg)
    def _recv_directed_signal(self, tag, src, value):
        self._directed_signal.emit((tag,src,value))

    def set_cached(self, name, value):
        self._cached_var[name]=value
    def send_signal(self, tag, value, dst=None):
        self._signal_pool.signal(self.name,tag,value,dst=dst)

    def _sync_call(self, func, args, kwargs, sync, timeout):
        return self.call_in_thread_sync(func,args=args,kwargs=kwargs,sync=sync,timeout=timeout,tag="control.execute")
    def command(self, *args, **kwargs):
        self._sync_call(self.process_command,args,kwargs,sync=False)
    def query(self, *args, **kwargs):
        timeout=kwargs.pop("timeout",None)
        return self._sync_call(self.process_query,args,kwargs,sync=True,timeout=timeout)
    def get_cached(self, name):
        return self._cached_var.get(name)

    class CommandAccess(object):
        def __init__(self, parent, sync, timeout=None):
            object.__init__(self)
            self.parent=parent
            self.sync=sync
            self.timeout=timeout
            self._calls={}
        def __getattr__(self, name):
            if name not in self._calls:
                parent=self.parent
                device=self.parent.device
                def devcall(*args, **kwargs):
                    getattr(device,name).__call__(*args,**kwargs)
                def remcall(*args, **kwargs):
                    return parent._sync_call(devcall,args,kwargs,sync=self.sync,timeout=self.timeout)
                self._calls[name]=remcall
            return self._calls[name]