from ...core.gui.qt.thread import controller
from ...core.utils import files as file_utils
from ...core.fileio import logfile

from PyQt5 import QtCore
import numpy as np
import threading
import collections
from future.utils import viewitems
import os.path

class StreamFormerThread(controller.QThreadController):
    def __init__(self, name=None, setupargs=None, setupkwargs=None, signal_pool=None):
        controller.QThreadController.__init__(self,name=name,kind="loop",signal_pool=signal_pool)
        self.channels={}
        self.table={}
        self._channel_lock=threading.RLock()
        self._row_lock=threading.RLock()
        self._row_cnt=0
        self.block_period=1
        self._new_block_done.connect(self._on_new_block_slot,type=QtCore.Qt.QueuedConnection)
        self._new_row_done.connect(self._add_new_row,type=QtCore.Qt.QueuedConnection)
        self.setupargs=setupargs or []
        self.setupkwargs=setupkwargs or {}

    def setup(self):
        pass
    def on_new_row(self, row):
        return row
    _new_block_done=QtCore.pyqtSignal()
    @controller.exsafeSlot()
    def _on_new_block_slot(self):
        self.on_new_block()
    def on_new_block(self):
        pass
    def cleanup(self):
        pass

    def on_start(self):
        controller.QThreadController.on_start(self)
        self.setup(*self.setupargs,**self.setupkwargs)
    def on_finish(self):
        self.cleanup()

    Channel=collections.namedtuple("Channel",["data","func","required","max_len"])
    def add_channel(self, name, func=None, max_len=1):
        if name in self.channels:
            raise KeyError("channel {} already exists".format(name))
        self.channels[name]=self.Channel(collections.deque(),func,func is None,max_len)
        self.table[name]=[]
    def subscribe_source(self, name, srcs, dsts="any", tags=None, parse=None, filt=None):
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
        self._new_row_done.emit()
    _new_row_done=QtCore.pyqtSignal()
    @controller.exsafeSlot()
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
            if self.block_period and self._row_cnt>=self.block_period:
                self._row_cnt=0
                self._new_block_done.emit()



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





class TableAccumulator(object):
    def __init__(self, channels, memsize=1000000):
        object.__init__(self)
        self.channels=channels
        self.data=[[] for _ in channels]
        self.memsize=memsize

    def add_data(self, data):
        if isinstance(data,dict):
            table_data=[]
            for ch in self.channels:
                if ch not in data:
                    raise KeyError("data doesn't contain channel {}".format(ch))
                table_data.append(data[ch])
            data=table_data
        minlen=min([len(incol) for incol in data])
        for col,incol in zip(self.data,data):
            col.extend(incol[:minlen])
            if len(col)>self.memsize:
                del col[:len(col)-self.memsize]
        return minlen
    def reset_data(self, maxlen=0):
        for col in self.data:
            del col[:len(col)-maxlen]
    
    def get_data_columns(self, channels=None, maxlen=None):
        channels=channels or self.channels
        data=[]
        for ch in channels:
            col=self.data[self.channels.index(ch)]
            if maxlen is not None:
                col=col[len(col)-maxlen:]
            data.append(col)
        return data
    def get_data_rows(self, channels=None, maxlen=None):
        return list(zip(*self.get_data_columns(channels=channels,maxlen=maxlen)))
    def get_data_dict(self, channels=None, maxlen=None):
        channels=channels or self.channels
        return dict(zip(channels,self.get_data_columns(maxlen=maxlen)))


class TableAccumulatorThread(controller.QTaskThread):
    def setup_task(self, channels, data_source, memsize=1000000):
        self.channels=channels
        self.fmt=[None]*len(channels)
        self.table_accum=TableAccumulator(channels=channels,memsize=memsize)
        self.subscribe(self.accum_data,srcs=data_source,dsts="any",tags="points",limit_queue=1000)
        self.subscribe(self.on_source_reset,srcs=data_source,dsts="any",tags="reset")
        self.logger=None
        self.streaming=False
        self.resetting=False
        self.reset_maxlen=0
        self.add_command("start_streaming",self.start_streaming)
        self.add_command("stop_streaming",self.stop_streaming)
        self.add_command("reset_data",self.reset_data)
        self.data_lock=threading.Lock()

    def start_streaming(self, path, source_trigger=False, append=False):
        self.streaming=not source_trigger
        if not append and os.path.exists(path):
            file_utils.retry_remove(path)
        self.logger=logfile.LogFile(path)
    def stop_streaming(self):
        self.logger=None
        self.streaming=False

    
    def on_source_reset(self, src, tag, value):
        self.table_accum.reset_data()
        if self.logger and not self.streaming:
            self.streaming=True

    def accum_data(self, src, tag, value):
        with self.data_lock:
            added_len=self.table_accum.add_data(value)
        if self.logger and self.streaming:
            new_data=self.table_accum.get_data_rows(maxlen=added_len)
            self.logger.write_multi_datalines(new_data,columns=self.channels,add_timestamp=False,fmt=self.fmt)
    
    def reset_data(self, maxlen=0):
        with self.data_lock:
            self.table_accum.reset_data(maxlen=maxlen)

    def get_data_sync(self, channels=None, maxlen=None, fmt="rows"):
        with self.data_lock:
            if fmt=="columns":
                return self.table_accum.get_data_columns(channels=channels,maxlen=maxlen)
            elif fmt=="rows":
                return self.table_accum.get_data_rows(channels=channels,maxlen=maxlen)
            elif fmt=="dict":
                return self.table_accum.get_data_dict(channels=channels,maxlen=maxlen)
            else:
                raise ValueError("unrecognized data format: {}".format(fmt))