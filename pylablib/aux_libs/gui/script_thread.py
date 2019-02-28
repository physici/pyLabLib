from ...core.gui.qt.thread import controller, signal_pool
from ...core.utils import general

from PyQt5 import QtCore

import collections



class ScriptStopException(Exception):
    """Exception for stopping script execution"""

class ScriptThread(controller.QTaskThread):
    def __init__(self, name=None, setupargs=None, setupkwargs=None, signal_pool=None):
        controller.QTaskThread.__init__(self,name=name,setupargs=setupargs,setupkwargs=setupkwargs,signal_pool=signal_pool)
        self._monitor_signal.connect(self._on_monitor_signal)
        self._monitored_signals={}
        self.executing=False
        self.stop_request=False
        self.add_command("start_script",self._start_script)

    def process_message(self, tag, value):
        if tag=="control.start":
            self.c.start_script()
            if self.executing:
                self.stop_request=True
        if tag=="control.stop":
            self.stop_request=True
        return False
    def process_signal(self, src, tag, value):
        return False

    def setup_script(self, *args, **kwargs):
        pass
    def finalize_script(self):
        self.interrupt_script()
    def run_script(self):
        pass
    def interrupt_script(self):
        pass
    def check_stop(self):
        if self.stop_request:
            self.stop_request=False
            raise ScriptStopException()



    def setup_task(self, *args, **kwargs):
        self.setup_script(*args,**kwargs)
    def finalize_task(self):
        self.finalize_script()

    def _start_script(self):
        self.executing=True
        self.stop_request=False
        try:
            self.run_script()
        except ScriptStopException:
            pass
        finally:
            self.interrupt_script()
            self.executing=False

    _monitor_signal=QtCore.pyqtSignal("PyQt_PyObject")
    @QtCore.pyqtSlot("PyQt_PyObject")
    def _on_monitor_signal(self, value):
        mon,msg=value
        try:
            signal=self._monitored_signals[mon]
            if not signal.paused:
                signal.messages.append(msg)
        except KeyError:
            pass
    
    class MonitoredSignal(object):
        def __init__(self, uid):
            object.__init__(self)
            self.uid=uid
            self.messages=[]
            self.paused=True
    def add_signal_monitor(self, mon, srcs="any", dsts="any", tags=None, filt=None):
        if mon in self._monitored_signals:
            raise KeyError("signal monitor {} already exists".format(mon))
        uid=self.subscribe_nonsync(lambda *msg: self._monitor_signal.emit((mon,signal_pool.TSignal(*msg))),srcs=srcs,dsts=dsts,tags=tags,filt=filt)
        self._monitored_signals[mon]=self.MonitoredSignal(uid)
    def remove_signal_monitor(self, mon):
        if mon not in self._monitored_signals:
            raise KeyError("signal monitor {} doesn't exist".format(mon))
        uid,_=self._monitored_signals.pop(mon)
        self.unsubscribe(uid)
    TWaitResult=collections.namedtuple("TWaitResult",["monitor","message"])
    def wait_for_signal_monitor(self, mons, timeout=None):
        if not isinstance(mons,(list,tuple)):
            mons=[mons]
        for mon in mons:
            if mon not in self._monitored_signals:
                raise KeyError("signal monitor {} doesn't exist".format(mon))
        ctd=general.Countdown(timeout)
        while True:
            for mon in mons:
                if self._monitored_signals[mon].messages:
                    return self.TWaitResult(mon,self._monitored_signals[mon].messages.pop(0))
            self.wait_for_any_message(ctd.time_left())
    def new_monitored_signals_number(self, mon):
        if mon not in self._monitored_signals:
            raise KeyError("signal monitor {} doesn't exist".format(mon))
        return len(self._monitored_signals[mon].messages)
    def pop_monitored_signal(self, mon, n=None):
        if self.new_monitored_signals_number(mon):
            if n is None:
                return self._monitored_signals[mon].messages.pop(0)
            else:
                return [self._monitored_signals[mon].messages.pop(0) for _ in range(n)]
        return None
    def reset_monitored_signal(self, mon):
        self._monitored_signals[mon].messages.clear()
    def pause_monitoring(self, mon, paused=True):
        self._monitored_signals[mon].paused=paused
    def start_monitoring(self, mon):
        self.pause_monitoring(mon,paused=False)


    def start_execution(self):
        self.send_message("control.start",None)
    def stop_execution(self):
        self.send_message("control.stop",None)