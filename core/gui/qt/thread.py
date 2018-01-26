from ...mthread import notifier
from ...utils import general, funcargparse
from . import signal_pool, threadprop

from PyQt4 import QtCore

import threading
    
_depends_local=["...mthread.notifier"]

_default_signal_pool=signal_pool.SignalPool()

class QThreadControllerThread(QtCore.QThread):
    finalized=QtCore.pyqtSignal()
    stop_request=QtCore.pyqtSignal()
    def __init__(self, controller):
        QtCore.QThread.__init__(self)
        self.controller=controller
        threadprop.get_app().aboutToQuit.connect(self.quit_sync)
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
    def __init__(self, name=None, kind="loop", signal_pool=None):
        QtCore.QObject.__init__(self)
        self.name=name or threadprop._thread_uids(type(self).__name__)
        funcargparse.check_parameter_range(kind,"kind",{"loop","run","main"})
        self.kind=kind
        if self.kind=="main":
            if not threadprop.is_gui_thread():
                raise threadprop.ThreadError("GUI thread controller can only be created in the main thread")
            if threadprop.current_controller(require_controller=False):
                raise threadprop.DuplicateControllerThreadError()
            self.thread=threadprop.get_gui_thread()
            threadprop._local_data.controller=self
        else:
            self.thread=QThreadControllerThread(self)
        self._wait_timer=QtCore.QTimer(self)
        self._wait_timer.setSingleShot(True)
        self._wait_timer.timeout.connect(self._on_wait_timeout)
        self._message_queue={}
        self._sync_queue={}
        self._sync_clearance=set()
        self._exec_notes={}
        self._exec_notes_lock=threading.Lock()
        self._signal_pool=signal_pool or _default_signal_pool
        self._signal_pool_uids=[]
        self._stopped=(self.kind!="main")
        self.moveToThread(self.thread)
        self.messaged.connect(self._get_message)
        self.interrupt_called.connect(self._on_call_in_thread)
        self.thread.started.connect(self._on_start_event)
        if self.kind=="main":
            threadprop.get_app().aboutToQuit.connect(self._on_finish_event)
            threadprop.get_app().lastWindowClosed.connect(self._on_last_window_closed)
        else:
            self.thread.finalized.connect(self._on_finish_event)
        
    @QtCore.pyqtSlot()
    def _on_wait_timeout(self):
        pass
    messaged=QtCore.pyqtSignal("PyQt_PyObject")
    @QtCore.pyqtSlot("PyQt_PyObject")
    def _get_message(self, msg):
        kind,tag,value=msg
        if kind=="msg":
            if tag.startswith("interrupt."):
                self._process_interrupt(tag[len("interrupt."):],value)
                return
            if self.process_message(tag,value):
                return
            self._message_queue.setdefault(tag,[]).append(value)
        elif kind=="sync":
            if (tag,value) in self._sync_clearance:
                self._sync_clearance.remove((tag,value))
            else:
                self._sync_queue.setdefault(tag,set()).add(value)
        elif kind=="stop":
            self._stopped=True
    interrupt_called=QtCore.pyqtSignal("PyQt_PyObject")
    @QtCore.pyqtSlot("PyQt_PyObject")
    def _on_call_in_thread(self, call):
        call()
    @QtCore.pyqtSlot()
    def _on_start_event(self):
        self._stopped=False
        threadprop._local_data.controller=self
        threadprop.register_controller(self)
        self.notify_exec("start")
        try:
            self.on_start()
            if self.kind=="run":
                self._do_run()
                self.thread.stop_request.emit()
        except threadprop.InterruptExceptionStop:
            self.thread.stop_request.emit()
    @QtCore.pyqtSlot()
    def _on_finish_event(self):
        self.on_finish()
        for uid in self._signal_pool_uids:
            self._signal_pool.unsubscribe(uid)
        self.notify_exec("stop")
        threadprop.unregister_controller(self)
    @QtCore.pyqtSlot()
    def _on_last_window_closed(self):
        if threadprop.get_app().quitOnLastWindowClosed():
            self._request_stop()
    

    def is_controlled(self):
        return QtCore.QThread.currentThread() is self.thread

    def _process_interrupt(self, tag, value):
        if tag=="execute":
            value()
    def process_message(self, tag, value):
        return False
    def on_start(self):
        pass
    def on_finish(self):
        pass
    def run(self):
        pass

    def _do_run(self):
        self.run()
    def _wait_for_any_msg(self, is_done, timeout=None):
        self.check_messages()
        ctd=general.Countdown(timeout)
        while True:
            if self._stopped:
                raise threadprop.InterruptExceptionStop()
            done,value=is_done()
            if done:
                return value
            if timeout is not None:
                time_left=ctd.time_left()
                if time_left:
                    self._wait_timer.start(int(time_left*1E3))
                    threadprop.get_app().processEvents(QtCore.QEventLoop.WaitForMoreEvents)
                else:
                    raise threadprop.TimeoutThreadError()
            else:
                threadprop.get_app().processEvents(QtCore.QEventLoop.WaitForMoreEvents)
    def wait_for_message(self, tag, timeout=None):
        def is_done():
            if self._message_queue.setdefault(tag,[]):
                value=self._message_queue[tag].pop(0)
                return True,value
            return False,None
        self._wait_for_any_msg(is_done,timeout=timeout)
    def new_messages_number(self, tag):
        return len(self._message_queue.setdefault(tag,[]))
    def pop_message(self, tag):
        if self.new_messages_number(tag):
            return self._message_queue[tag].pop(0)
        raise threadprop.NoMessageThreadError("no messages with tag '{}'".format(tag))
    def wait_for_sync(self, tag, uid, timeout=None):
        def is_done():
            if uid in self._sync_queue.setdefault(tag,set()):
                self._sync_queue[tag].remove(uid)
                return True,None
            return False,None
        try:
            self._wait_for_any_msg(is_done,timeout=timeout)
        except threadprop.TimeoutThreadError:
            self._sync_clearance.add((tag,uid))
    def check_messages(self):
        threadprop.get_app().processEvents(QtCore.QEventLoop.AllEvents)
        if self._stopped:
            raise threadprop.InterruptExceptionStop()
    def sleep(self, time):
        def is_done():
            return False,None
        try:
            self._wait_for_any_msg(is_done,timeout=time)
        except threadprop.TimeoutThreadError:
            pass

    def subscribe(self, callback, srcs=None, tags=None, filt=None, priority=0, limit_queue=1, limit_period=0, id=None):
        if self._signal_pool:
            uid=self._signal_pool.subscribe(callback,srcs=srcs,dsts=self.name,tags=tags,filt=filt,priority=priority,
                limit_queue=limit_queue,limit_period=limit_period,dest_controller=self,id=id)
            self._signal_pool_uids.append(uid)
            return uid
    def subscribe_nonsync(self, callback, srcs=None, dsts=None, tags=None, filt=None, priority=0, id=None):
        if self._signal_pool:
            uid=self._signal_pool.subscribe_nonsync(callback,srcs=srcs,dsts=self.name,tags=tags,filt=filt,priority=priority,id=id)
            self._signal_pool_uids.append(uid)
            return uid
    def unsubscribe(self, id):
        self._signal_pool.unsubscribe(id)
    def send_signal(self, tag, value, dst=None):
        self._signal_pool.signal(self.name,tag,value,dst=dst)

    def send_message(self, tag, value):
        self.messaged.emit(("msg",tag,value))
    def send_sync(self, tag, uid):
        self.messaged.emit(("sync",tag,uid))

    def start(self):
        self.thread.start()
    def _request_stop(self):
        self.messaged.emit(("stop",None,None))
    def stop(self):
        if self.kind=="main":
            threadprop.get_app().exit()
        else:
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

    def call_in_thread_callback(self, func, args=None, kwargs=None, callback=None, tag=None):
        def call():
            func(*(args or []),**(kwargs or {}))
            if callback:
                callback()
        if tag is None:
            self.interrupt_called.emit(call)
        else:
            self.send_message(tag,call)
    def call_in_thread_sync(self, func, args=None, kwargs=None, sync=True, timeout=None, default_result=None, pass_exception=True, tag=None, same_thread_shortcut=True):
        if same_thread_shortcut and sync and threadprop.current_controller() is self:
            return func(*(args or []),**(kwargs or {}))
        call=QSyncCall(func,args=args,kwargs=kwargs,pass_exception=pass_exception)
        if tag is None:
            self.interrupt_called.emit(call)
        else:
            self.send_message(tag,call)
        return call.value(sync=sync,timeout=timeout,default=default_result)


class QThreadNotifier(notifier.ISkippableNotifier):
    _uid_gen=general.UIDGenerator(thread_safe=True)
    _notify_tag="_thread_notifier"
    def __init__(self, skippable=True):
        notifier.ISkippableNotifier.__init__(self,skippable=skippable)
        self._uid=None
        self.value=None
    def _pre_wait(self, *args, **kwargs):
        self._controller=threadprop.current_controller(require_controller=True)
        self._uid=self._uid_gen()
        return True
    def _do_wait(self, timeout=None):
        try:
            self._controller.wait_for_sync(self._notify_tag,self._uid,timeout=timeout)
            return True
        except threadprop.TimeoutThreadError:
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
            if self._state:
                return True
            n=QThreadNotifier()
            self._notifiers.append(n)
        return n.wait(timeout=timeout)
    def notify(self):
        with self._lock:
            if self._state:
                return
            self._state=True
        while self._notifiers:
            self._notifiers.pop().notify()

class QSyncCall(object):
    def __init__(self, func, args=None, kwargs=None, pass_exception=True):
        object.__init__(self)
        self.func=func
        self.args=args or []
        self.kwargs=kwargs or {}
        self.synchronizer=QThreadNotifier()
        self.pass_exception=pass_exception
    def __call__(self):
        try:
            res=("fail",None)
            res=("result",self.func(*self.args,**self.kwargs))
        except Exception as e:
            res=("exception",e)
        finally:
            self.synchronizer.notify(res)
    def value(self, sync=True, timeout=None, default=None):
        if sync:
            if self.synchronizer.wait(timeout):
                kind,value=self.synchronizer.get_value()
                if kind=="result":
                    return value
                elif kind=="exception" and self.pass_exception:
                    raise value
            else:
                return default
        else:
            return self.synchronizer
    def wait(self, timeout=None):
        return self.synchronizer.wait(timeout)
    def done(self):
        return self.synchronizer.done_wait()







class QMultiRepeatingThreadController(QThreadController):
    _new_jobs_check_period=0.1
    def __init__(self, name=None, setup=None, cleanup=None, args=None, kwargs=None, self_as_arg=False, signal_pool=None):
        QThreadController.__init__(self,name,kind="run",signal_pool=signal_pool)
        self.setup=setup
        self.cleanup=cleanup
        self.paused=False
        self.single_shot=False
        self.args=args or []
        if self_as_arg:
            self.args=[self]+self.args
        self.kwargs=kwargs or {}
        self.jobs={}
        self.timers={}
        self._jobs_list=[]
        
    def add_job(self, name, job, period):
        if name in self.jobs:
            raise ValueError("job {} already exists".format(name))
        self.jobs[name]=(job,period)
        self.timers[name]=general.Timer(period)
        self._jobs_list.append(name)
    
    def _get_next_job(self):
        if not self._jobs_list:
            return None,None
        idx=None
        left=None
        for i,n in enumerate(self._jobs_list):
            t=self.timers[n]
            l=t.time_left()
            if l==0:
                idx,left=i,0
                break
            elif (left is None) or (l<left):
                idx=i
                left=l
        n=self._jobs_list.pop(idx)
        self._jobs_list.append(n)
        return n,left
    
    def on_start(self):
        if self.setup:
            self.setup(*self.args,**self.kwargs)
    def run(self):
        while True:
            name,to=self._get_next_job()
            if name is None:
                self.sleep(self._new_jobs_check_period)
            else:
                self.sleep(to)
                job=self.jobs[name][0]
                self.timers[name].acknowledge(nmin=1)
                job(*self.args,**self.kwargs)
            while self.new_messages_number("control.execute"):
                self.pop_message("control.execute")()
    def on_finish(self):
        if self.cleanup:
            self.cleanup(*self.args,**self.kwargs)