from ...mthread import notifier
from ...utils import general

from PyQt4 import QtCore

import threading
    
_depends_local=["...thread.controller"]


### Errors ###
class ThreadError(RuntimeError):
    """
    Generic thread error.
    """
    def __init__(self, msg=None):
        msg=msg or "thread error"
        RuntimeError.__init__(self, msg)
        
class NotRunningThreadError(ThreadError):
    """
    Thread error for a case of a missing or stopped thread.
    """
    def __init__(self, msg=None):
        msg=msg or "thread is not running"
        ThreadError.__init__(self, msg)
class NoControllerThreadError(ThreadError):
    """
    Thread error for a case of thread having no conrollers.
    """
    def __init__(self, msg=None):
        msg=msg or "thread has no controller"
        ThreadError.__init__(self, msg)
class TimeoutThreadError(ThreadError):
    """
    Thread error for a case of a wait timeout.
    """
    def __init__(self, msg=None):
        msg=msg or "waiting has timed out"
        ThreadError.__init__(self, msg)

### Interrupts ###
class InterruptException(Exception):
    """
    Generic interrupt exception (raised by some function to signal interrupts from other threads).
    """
    def __init__(self, msg=None):
        msg=msg or "thread interrupt"
        Exception.__init__(self, msg)
class InterruptExceptionStop(InterruptException):
    """
    Interrupt exception denoting thread stop request.
    """
    def __init__(self, msg=None):
        msg=msg or "thread interrupt: stop"
        InterruptException.__init__(self, msg)


def get_app():
    """
    Get current application instance.
    """
    return QtCore.QCoreApplication.instance()
def is_gui_running():
    """
    Check if GUI is running.
    """
    return get_app() is not None
def is_gui_thread():
    """
    Check if the current thread is the one running the GUI loop.
    """
    app=get_app()
    return (app is not None) and (QtCore.QThread.currentThread() is app.thread())
def current_controller(require_controller=True):
    controller=getattr(QtCore.QThread.currentThread(),"controller",None)
    if require_controller and controller is None:
        raise NoControllerThreadError("current thread has no controller")
    return controller
    

_thread_uids=general.NamedUIDGenerator(thread_safe=True)
_running_threads={}
class QThreadControllerThread(QtCore.QThread):
    finalized=QtCore.pyqtSignal()
    stop_request=QtCore.pyqtSignal()
    def __init__(self, controller):
        QtCore.QThread.__init__(self)
        self.controller=controller
        get_app().aboutToQuit.connect(self.quit_sync)
        self.stop_request.connect(self.quit_sync)
    def run(self):
        try:
            QtCore.QThread.run(self)
        finally:
            self.finalized.emit()
    def quit_sync(self):
        if self.isRunning():
            self.quit()
            self.controller._request_stop()
            self.wait()
            

class QThreadController(QtCore.QObject):
    def __init__(self, name=None, looped=True):
        QtCore.QObject.__init__(self)
        self.name=name or _thread_uids(type(self).__name__)
        self.thread=QThreadControllerThread(self)
        self._message_queue={}
        self._sync_queue={}
        self._sync_clearance=set()
        self._stopped=True
        self.looped=looped
        self.moveToThread(self.thread)
        self.messaged.connect(self._get_message)
        self.thread.started.connect(self._on_start_event)
        self.thread.finalized.connect(self._on_finish_event)
        self._exec_notes={}
        self._exec_notes_lock=threading.Lock()
        
    messaged=QtCore.pyqtSignal("PyQt_PyObject")
    @QtCore.pyqtSlot("PyQt_PyObject")
    def _get_message(self, msg):
        kind,tag,value=msg
        if kind=="stop":
            self._stopped=True
        if kind=="msg":
            if self.process_message(tag,value):
                return
            self._message_queue.setdefault(tag,[]).append(value)
        elif kind=="sync":
            if (tag,value) in self._sync_clearance:
                self._sync_clearance.remove((tag,value))
            else:
                self._sync_queue.setdefault(tag,set()).add(value)
    @QtCore.pyqtSlot()
    def _on_start_event(self):
        self.notify_exec("start")
        self.on_start()
        if not self.looped:
            self._do_run()
            self.thread.stop_request.emit()
    @QtCore.pyqtSlot()
    def _on_finish_event(self):
        self.on_finish()
        self.notify_exec("stop")

    def is_controlled(self):
        return QtCore.QThread.currentThread() is self.thread

    def process_message(self, tag, value):
        return False
    def on_start(self):
        pass
    def on_finish(self):
        pass
    def run(self):
        pass

    def _do_run(self):
        try:
            self._stopped=False
            self.run()
        except InterruptExceptionStop:
            pass
    def _wait_for_any_msg(self, is_done, timeout=None):
        ctd=general.Countdown(timeout)
        while True:
            if self._stopped:
                raise InterruptExceptionStop()
            done,value=is_done()
            if done:
                return value
            if timeout is not None:
                time_left=ctd.time_left()
                if time_left:
                    get_app().processEvents(QtCore.QEventLoop.WaitForMoreEvents,time_left*1E3)
                else:
                    raise TimeoutThreadError()
            else:
                get_app().processEvents(QtCore.QEventLoop.WaitForMoreEvents)
    def wait_for_message(self, tag, timeout=None):
        def is_done():
            if self._message_queue.setdefault(tag,[]):
                value=self._message_queue[tag].pop(0)
                return True,value
            return False,None
        self._wait_for_any_msg(is_done,timeout=timeout)
    def wait_for_sync(self, tag, uid, timeout=None):
        def is_done():
            if uid in self._sync_queue.setdefault(tag,set()):
                self._sync_queue[tag].remove(uid)
                return True,None
            return False,None
        try:
            self._wait_for_any_msg(is_done,timeout=timeout)
        except TimeoutThreadError:
            self._sync_clearance.add((tag,uid))
    def check_messages(self):
        get_app().processEvents(QtCore.QEventLoop.AllEvents)
        if self._stopped:
            raise InterruptExceptionStop()
    def sleep(self, time):
        def is_done():
            return False,None
        try:
            self._wait_for_any_msg(is_done,timeout=time)
        except TimeoutThreadError:
            pass
    def send_message(self, tag, value):
        self.messaged.emit(("msg",tag,value))
    def send_sync(self, tag, uid):
        self.messaged.emit(("sync",tag,uid))

    def start(self):
        self.thread.start()
    def _request_stop(self):
        self.messaged.emit(("stop",None,None))
    def stop(self):
        self.thread.quit_sync()
    
    def _get_exec_note(self, point):
        with self._exec_notes_lock:
            if point not in self._exec_notes:
                self._exec_notes[point]=QMultiThreadNotifier()
            return self._exec_notes[point]
    def notify_exec(self, point):
        self._get_exec_note(point).notify()
    def sync_exec(self, point, timeout=None):
        return self._get_exec_note(point).wait(timeout=timeout)


class QThreadNotifier(notifier.ISkippableNotifier):
    _uid_gen=general.UIDGenerator(thread_safe=True)
    _notify_tag="_thread_notifier"
    def __init__(self):
        notifier.ISkippableNotifier.__init__(self,skippable=True)
        self._wait_thread=True
        self._uid=None
        self.value=None
    def _pre_wait(self, *args, **kwargs):
        self._controller=current_controller(require_controller=True)
        self._uid=self._uid_gen()
        return True
    def _do_wait(self, timeout=None):
        try:
            self._controller.wait_for_sync(self._notify_tag,self._uid,timeout=timeout)
            return True
        except TimeoutThreadError:
            return False
    def _pre_notify(self, value=None):
        self.value=value
    def _do_notify(self, *args, **kwargs):
        self._controller.send_sync(self._notify_tag,self._uid)
        return True
    def get_value(self):
        return self.value

class QMultiThreadNotifier(object):
    def __init__(self):
        object.__init__(self)
        self._lock=threading.Lock()
        self._state=False
        self._notifiers=[]
    def wait(self, timeout=None):
        with self._lock:
            if self.state:
                return True
            n=QThreadNotifier()
            self._notifiers.append(n)
        return n.wait(timeout=timeout)
    def notify(self):
        with self._lock:
            if self._state:
                return
            self.state=True
        while self._notifiers:
            self._notifiers.pop().notify()
