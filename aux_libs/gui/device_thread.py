from ...core.gui.qt.thread import controller, threadprop
from ...core.utils import general

from PyQt4 import QtCore
import numpy as np

from future.utils import viewitems
import threading
import collections

class DeviceThread(controller.QMultiRepeatingThreadController):
    def __init__(self, name=None, devargs=None, devkwargs=None, signal_pool=None):
        controller.QMultiRepeatingThreadController.__init__(self,name=name,signal_pool=signal_pool)
        self.devargs=devargs or []
        self.devkwargs=devkwargs or {}
        self.device=None
        self._cached_var={}
        self._cached_exp={}
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
    def process_interrupt(self, *args, **kwargs):
        pass
    def close_device(self):
        if self.device is not None:
            self.device.close()

    def on_start(self):
        self.setup_device(*self.devargs,**self.devkwargs)
        self.subscribe_nonsync(self._recv_directed_signal)
    def on_finish(self):
        self.close_device()

    _directed_signal=QtCore.pyqtSignal("PyQt_PyObject")
    @QtCore.pyqtSlot("PyQt_PyObject")
    def _on_directed_signal(self, msg):
        self.process_signal(*msg)
    def _recv_directed_signal(self, tag, src, value):
        self._directed_signal.emit((tag,src,value))

    _cached_change_tag="#sync.wait.cached"
    def set_cached(self, name, value, notify=False, notify_tag="changed.*"):
        self._cached_var[name]=value
        for ctl in self._cached_exp.get(name,[]):
            ctl.send_message(self._cached_change_tag,value)
        if notify:
            notify_tag.replace("*",name)
            self.send_signal("any",notify_tag,value)

    def _sync_call(self, func, args, kwargs, sync, timeout=None):
        return self.call_in_thread_sync(func,args=args,kwargs=kwargs,sync=sync,timeout=timeout,tag="control.execute")
    def command(self, *args, **kwargs):
        self._sync_call(self.process_command,args,kwargs,sync=False)
    def query(self, *args, **kwargs):
        timeout=kwargs.pop("timeout",None)
        return self._sync_call(self.process_query,args,kwargs,sync=True,timeout=timeout)
    def interrupt(self, *args, **kwargs):
        return self.call_in_thread_sync(self.process_interrupt,args,kwargs,sync=False)
    def get_cached(self, name):
        return self._cached_var.get(name)
    def wait_for_cached(self, name, pred, timeout=None):
        if not hasattr(pred,"__call__"):
            v=pred
            pred=lambda x: x==v
        ctl=threadprop.current_controller()
        with self._cached_var_lock:
            self._cached_exp.setdefault(name,[]).append(ctl)
        ctd=general.Countdown(timeout)
        try:
            while True:
                value=self.get_cached(name)
                if pred(value):
                    return value
                ctl.wait_for_message(self._cached_change_tag,timeout=ctd.time_left())
        finally:
            with self._cached_var_lock:
                self._cached_exp[name].remove(ctl)


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



class DataAccumulatorThread(controller.QThreadController):
    def __init__(self, name=None, signal_pool=None):
        controller.QThreadController.__init__(self,name=name,kind="loop",signal_pool=signal_pool)
        self.channels={}
        self.table={}
        self._channel_lock=threading.RLock()
        self._row_lock=threading.RLock()
        self._row_cnt=0
        self.block_period=1
        self.new_block_done.connect(self.on_new_block)
        self.new_row_done.connect(self._add_new_row)

    def setup(self):
        pass
    def on_new_row(self, row):
        return row
    new_block_done=QtCore.pyqtSignal()
    @QtCore.pyqtSlot()
    def on_new_block(self):
        pass
    def cleanup(self):
        pass

    def on_start(self):
        self.setup()
    def on_finish(self):
        self.cleanup()

    Channel=collections.namedtuple("Channel",["data","func","required","max_len"])
    def add_channel(self, name, func=None, required=True, max_len=1):
        if name in self.channels:
            raise KeyError("channel {} already exists".format(name))
        self.channels[name]=self.Channel(collections.deque(),func,required and (func is None),max_len)
        self.table[name]=[]
    def subscribe_channel(self, name, srcs, dsts="any", tags=None, parse=None, filt=None):
        def on_signal(src, tag, value):
            with self._channel_lock:
                self._add_data(name,src,tag,value,parse=parse)
        self.subscribe_nonsync(on_signal,srcs=srcs,dsts=dsts,tags=tags,filt=filt)

    def _complete_row(self, row):
        for n in self.channels:
            if n not in row:
                ch=self.channels[n]
                row[n]=None if ch.func is None else ch.func()
        return self.on_new_row(row)
    def _add_data(self, name, src, tag, value, parse=None):
        if parse is not None:
            row=parse(src,tag,value)
        else:
            row={name:value}
        added=False
        for name,value in viewitems(row):
            ch=self.channels[name]
            ch.data.append(value)
            if ch.max_len and len(ch.data)>ch.max_len:
                ch.data.popleft()
            else:
                added=True
        if not added:
            return
        for _,ch in viewitems(self.channels):
            if ch.required and not ch.data:
                return
        self.new_row_done.emit()
    new_row_done=QtCore.pyqtSignal()
    def _add_new_row(self):
        with self._channel_lock:
            row={}
            for n,ch in viewitems(self.channels):
                if ch.data:
                    row[n]=ch.data.popleft()
        row=self._complete_row(row)
        with self._row_lock:
            for n,t in viewitems(self.table):
                t.append(row[n])
            self._row_cnt+=1
            if self.block_period and self._row_cnt>self.block_period:
                self._row_cnt=0
                self.new_block_done.emit()



    def get_data(self, nrows=None, columns=None, copy=True):
        if columns is None and nrows is None:
            return self.table.copy() if copy else self.table
        with self._row_lock:
            if nrows is None:
                nrows=len(self.table.values()[0])
            if columns is None:
                return dict((n,v[:nrows]) for n,v in viewitems(self.table))
            else:
                return np.column_stack([self.table[c][:nrows] for c in columns])
    def pop_data(self, nrows=None, columns=None):
        if nrows is None:
            with self._row_lock:
                table=self.table
                self.table=dict([(n,[]) for n in table])
            if columns is None:
                return dict((n,v) for n,v in viewitems(table))
            else:
                return np.column_stack([table[c] for c in columns])
        with self._row_lock:
            res=self.get_data(nrows=nrows,columns=columns)
            for n,c in viewitems(self.table):
                del c[:nrows]
            return res
    def clear_data(self):
        with self._row_lock:
            self.table=dict([(n,[]) for n in self.table])

    def clear_all(self):
        with self._row_lock:
            for _,ch in viewitems(self.channels):
                ch.data.clear()