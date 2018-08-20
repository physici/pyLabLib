from ...core.gui.qt.thread import controller,signal_pool,synchronizing
from ...core.utils import general

from PyQt5 import QtCore



class ScriptStopException(Exception):
    """Exception for stopping script execution"""

class ScriptThread(controller.QTaskThread):
    def __init__(self, name=None, setupargs=None, setupkwargs=None, signal_pool=None):
        controller.QTaskThread.__init__(self,name=name,setupargs=setupargs,setupkwargs=setupkwargs,signal_pool=signal_pool)
        self._monitor_signal.connect(self._on_monitor_signal)
        self._monitored_signals={}
        self.running=False
        self.stop_request=False
        self.add_command("start_script",self._start_script)

    def process_message(self, tag, value):
        if tag=="control.start":
            self.c.start_script()
            if self.running:
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
        self.running=True
        try:
            self.run_script()
        except ScriptStopException:
            pass
        finally:
            self.interrupt_script()
        self.running=False

    _monitor_signal=QtCore.pyqtSignal("PyQt_PyObject")
    @QtCore.pyqtSlot("PyQt_PyObject")
    def _on_monitor_signal(self, value):
        mon,msg=value
        try:
            self._monitored_signals[mon][1].append(msg)
        except KeyError:
            pass
    
    def add_signal_monitor(self, mon, srcs="any", dsts="any", tags=None, filt=None):
        if mon in self._monitored_signals:
            raise KeyError("signal monitor {} already exists".format(mon))
        uid=self.subscribe_nonsync(lambda *msg: self._monitor_signal.emit((mon,signal_pool.Signal(*msg))),srcs=srcs,dsts=dsts,tags=tags,filt=filt)
        self._monitored_signals[mon]=(uid,[])
    def remove_signal_monitor(self, mon):
        if mon not in self._monitored_signals:
            raise KeyError("signal monitor {} doesn't exist".format(mon))
        uid,_=self._monitored_signals.pop(mon)
        self.unsubscribe(uid)
    def wait_for_signal_monitor(self, mons, timeout=None):
        if not isinstance(mons,(list,tuple)):
            mons=[mons]
        for mon in mons:
            if mon not in self._monitored_signals:
                raise KeyError("signal monitor {} doesn't exist".format(mon))
        ctd=general.Countdown(timeout)
        while True:
            self.wait_for_any_message(ctd.time_left())
            for mon in mons:
                if self._monitored_signals[mon][1]:
                    return (mon,self._monitored_signals[mon][1].pop(0))
    def new_monitored_signals_number(self, mon):
        if mon not in self._monitored_signals:
            raise KeyError("signal monitor {} doesn't exist".format(mon))
        return len(self._monitored_signals[mon][1])
    def pop_monitored_signal(self, mon):
        if self.new_monitored_signals_number(mon):
            return self._monitored_signals[mon][1].pop(0)
        return None


    def start_execution(self):
        self.send_message("control.start",None)
    def stop_execution(self):
        self.send_message("control.stop",None)