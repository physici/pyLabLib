from ....utils import general, funcargparse
from . import signal_pool, threadprop, synchronizing

from PyQt4 import QtCore

import threading
import time
    
_depends_local=["....mthread.notifier"]

_default_signal_pool=signal_pool.SignalPool()

_created_threads={}
_running_threads={}
_running_threads_lock=threading.Lock()
_running_threads_notifier=synchronizing.QMultiThreadNotifier()
_running_threads_stopping=False

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
            if self.currentThread() is not self:
                self.wait()
            

class QThreadController(QtCore.QObject):
    def __init__(self, name=None, kind="loop", signal_pool=None):
        QtCore.QObject.__init__(self)
        self.name=name or threadprop._thread_uids(type(self).__name__)
        funcargparse.check_parameter_range(kind,"kind",{"loop","run","main"})
        self.kind=kind
        store_created_controller(self)
        if self.kind=="main":
            if not threadprop.is_gui_thread():
                raise threadprop.ThreadError("GUI thread controller can only be created in the main thread")
            if threadprop.current_controller(require_controller=False):
                raise threadprop.DuplicateControllerThreadError()
            self.thread=threadprop.get_gui_thread()
            threadprop._local_data.controller=self
            register_controller(self)
        else:
            self.thread=QThreadControllerThread(self)
        # self._wait_timer=QtCore.QTimer(self)
        # self._wait_timer.setSingleShot(True)
        # self._wait_timer.timeout.connect(self._on_wait_timeout)
        self._wait_timer=QtCore.QBasicTimer()
        self._message_queue={}
        self._sync_queue={}
        self._sync_clearance=set()
        self._exec_notes={}
        self._exec_notes_lock=threading.Lock()
        self._signal_pool=signal_pool or _default_signal_pool
        self._signal_pool_uids=[]
        self._stopped=(self.kind!="main")
        self._running=not self._stopped
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
    started=QtCore.pyqtSignal()
    @QtCore.pyqtSlot()
    def _on_start_event(self):
        self._stopped=False
        threadprop._local_data.controller=self
        try:
            register_controller(self)
            self.notify_exec("start")
            self._running=True
            self.on_start()
            self.started.emit()
            self.notify_exec("run")
            if self.kind=="run":
                self._do_run()
                self.thread.stop_request.emit()
        except threadprop.InterruptExceptionStop:
            self.thread.stop_request.emit()
    finished=QtCore.pyqtSignal()
    @QtCore.pyqtSlot()
    def _on_finish_event(self):
        is_stopped=self._stopped
        self._stopped=False
        self.finished.emit()
        try:
            self.on_finish()
        finally:
            self._stopped=is_stopped
            self._running=False
            for uid in self._signal_pool_uids:
                self._signal_pool.unsubscribe(uid)
            self.notify_exec("stop")
            unregister_controller(self)
            if self.kind=="main":
                stop_all_controllers()
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
    def _wait_in_process_loop(self, is_done, timeout=None):
        ctd=general.Countdown(timeout)
        while True:
            if self._stopped:
                raise threadprop.InterruptExceptionStop()
            if timeout is not None:
                time_left=ctd.time_left()
                if time_left:
                    self._wait_timer.start(max(int(time_left*1E3),1),self)
                    threadprop.get_app().processEvents(QtCore.QEventLoop.WaitForMoreEvents)
                    self._wait_timer.stop()
                else:
                    self.check_messages()
                    raise threadprop.TimeoutThreadError()
            else:
                threadprop.get_app().processEvents(QtCore.QEventLoop.WaitForMoreEvents)
            done,value=is_done()
            if done:
                return value
    def wait_for_message(self, tag, timeout=None):
        def is_done():
            if self._message_queue.setdefault(tag,[]):
                value=self._message_queue[tag].pop(0)
                return True,value
            return False,None
        return self._wait_in_process_loop(is_done,timeout=timeout)
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
            self._wait_in_process_loop(is_done,timeout=timeout)
        except threadprop.TimeoutThreadError:
            self._sync_clearance.add((tag,uid))
            raise
    def wait_for_any_message(self, timeout=None):
        self._wait_in_process_loop(lambda: (True,None),timeout=timeout)
    def wait_until(self, check, timeout=None):
        self._wait_in_process_loop(lambda: (check(),None),timeout=timeout)
    def check_messages(self):
        threadprop.get_app().processEvents(QtCore.QEventLoop.AllEvents)
        if self._stopped:
            raise threadprop.InterruptExceptionStop()
    def sleep(self, timeout):
        try:
            self._wait_in_process_loop(lambda: (False,None),timeout=timeout)
        except threadprop.TimeoutThreadError:
            pass

    def subscribe(self, callback, srcs="any", dsts=None, tags=None, filt=None, priority=0, limit_queue=1, limit_period=0, id=None):
        if self._signal_pool:
            uid=self._signal_pool.subscribe(callback,srcs=srcs,dsts=dsts or self.name,tags=tags,filt=filt,priority=priority,
                limit_queue=limit_queue,limit_period=limit_period,dest_controller=self,id=id)
            self._signal_pool_uids.append(uid)
            return uid
    def subscribe_nonsync(self, callback, srcs="any", dsts=None, tags=None, filt=None, priority=0, id=None):
        if self._signal_pool:
            uid=self._signal_pool.subscribe_nonsync(callback,srcs=srcs,dsts=dsts or self.name,tags=tags,filt=filt,priority=priority,id=id)
            self._signal_pool_uids.append(uid)
            return uid
    def unsubscribe(self, id):
        self._signal_pool_uids.pop(id)
        self._signal_pool.unsubscribe(id)
    def send_signal(self, dst, tag, value=None, src=None):
        self._signal_pool.signal(src or self.name,dst,tag,value)

    def send_message(self, tag, value):
        self.messaged.emit(("msg",tag,value))
    def send_sync(self, tag, uid):
        self.messaged.emit(("sync",tag,uid))
    def poke(self):
        self.message.emit(("poke",None,None))

    def start(self):
        self.thread.start()
    def _request_stop(self):
        self.messaged.emit(("stop",None,None))
    def stop(self):
        if self.kind=="main":
            self.call_in_thread_callback(threadprop.get_app().quit)
        else:
            self.thread.quit_sync()
    def running(self):
        return self._running
    
    def _get_exec_note(self, point):
        with self._exec_notes_lock:
            if point not in self._exec_notes:
                self._exec_notes[point]=synchronizing.QMultiThreadNotifier()
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
        call=synchronizing.QSyncCall(func,args=args,kwargs=kwargs,pass_exception=pass_exception)
        if tag is None:
            self.interrupt_called.emit(call)
        else:
            self.send_message(tag,call)
        return call.value(sync=sync,timeout=timeout,default=default_result)





class QMultiRepeatingThreadController(QThreadController):
    _new_jobs_check_period=0.1
    def __init__(self, name=None, setup=None, cleanup=None, args=None, kwargs=None, self_as_arg=False, signal_pool=None):
        QThreadController.__init__(self,name,kind="run",signal_pool=signal_pool)
        self.sync_period=0
        self._last_sync_time=0
        self.setup=setup
        self.cleanup=cleanup
        self.args=args or []
        if self_as_arg:
            self.args=[self]+self.args
        self.kwargs=kwargs or {}
        self.jobs={}
        self.timers={}
        self._jobs_list=[]
        self.batch_jobs={}
        self._batch_jobs_args={}
        
    def add_job(self, name, job, period, initial_call=True):
        if name in self.jobs:
            raise ValueError("job {} already exists".format(name))
        self.jobs[name]=job
        self.timers[name]=general.Timer(period)
        self._jobs_list.append(name)
        if initial_call:
            job()
    def change_job_period(self, name, period):
        if name not in self.jobs:
            raise ValueError("job {} doesn't exists".format(name))
        self.timers[name].change_period(period)
    def remove_job(self, name):
        if name not in self.jobs:
            raise ValueError("job {} doesn't exists".format(name))
        self._jobs_list.remove(name)
        del self.jobs[name]
        del self.timers[name]

    def add_batch_job(self, name, job, cleanup=None):
        if name in self.jobs or name in self.batch_jobs:
            raise ValueError("job {} already exists".format(name))
        self.batch_jobs[name]=(job,cleanup)
    def start_batch_job(self, name, period, *args, **kwargs):
        if name not in self.batch_jobs:
            raise ValueError("job {} doesn't exists".format(name))
        if name in self.jobs:
            self.stop_batch_job(name)
        self._batch_jobs_args[name]=(args,kwargs)
        job=self.batch_jobs[name][0]
        gen=job(*args,**kwargs)
        def do_step():
            try:
                p=gen.next()
                if p is not None:
                    self.change_job_period(name,p)
            except StopIteration:
                self.stop_batch_job(name)
        self.add_job(name,do_step,period)
    def batch_job_running(self, name):
        if name not in self.batch_jobs:
            raise ValueError("job {} doesn't exists".format(name))
        return name in self.jobs
    def stop_batch_job(self, name, error_on_stopped=False):
        if name not in self.batch_jobs:
            raise ValueError("job {} doesn't exists".format(name))
        if name not in self.jobs:
            if error_on_stopped:
                raise ValueError("job {} doesn't exists".format(name))
            return
        self.remove_job(name)
        args,kwargs=self._batch_jobs_args.pop(name)
        cleanup=self.batch_jobs[name][1]
        if cleanup:
            cleanup(*args,**kwargs)
    
    def _get_next_job(self, ct):
        if not self._jobs_list:
            return None,None
        idx=None
        left=None
        for i,n in enumerate(self._jobs_list):
            t=self.timers[n]
            l=t.time_left(ct)
            if l==0:
                idx,left=i,0
                break
            elif (left is None) or (l<left):
                idx=i
                left=l
        n=self._jobs_list.pop(idx)
        self._jobs_list.append(n)
        return n,left
    def check_commands(self):
        while self.new_messages_number("control.execute"):
            self.pop_message("control.execute")()
    
    def on_start(self):
        if self.setup:
            self.setup(*self.args,**self.kwargs)
    def run(self):
        while True:
            ct=time.time()
            name,to=self._get_next_job(ct)
            if name is None:
                self.sleep(self._new_jobs_check_period)
            else:
                if (self._last_sync_time is None) or (self._last_sync_time+self.sync_period<=ct):
                    self._last_sync_time=ct
                    if to:
                        self.sleep(to)
                    else:
                        self.check_messages()
                elif to:
                    time.sleep(to)
                job=self.jobs[name]
                self.timers[name].acknowledge(nmin=1)
                job(*self.args,**self.kwargs)
            self.check_commands()
    def on_finish(self):
        for n in self.batch_jobs:
            if n in self.jobs:
                self.stop_batch_job(n)
        if self.cleanup:
            self.cleanup(*self.args,**self.kwargs)



def store_created_controller(controller):
    with _running_threads_lock:
        if _running_threads_stopping:
            raise threadprop.InterruptExceptionStop()
        name=controller.name
        if (name in _running_threads) or (name in _created_threads):
            raise threadprop.DuplicateControllerThreadError("thread with name {} already exists".format(name))
        _created_threads[name]=controller
def register_controller(controller):
    with _running_threads_lock:
        if _running_threads_stopping:
            raise threadprop.InterruptExceptionStop()
        name=controller.name
        if name in _running_threads:
            raise threadprop.DuplicateControllerThreadError("thread with name {} already exists".format(name))
        if name not in _created_threads:
            raise threadprop.NoControllerThreadError("thread with name {} hasn't been created".format(name))
        _running_threads[name]=controller
        del _created_threads[name]
    _running_threads_notifier.notify()
def unregister_controller(controller):
    with _running_threads_lock:
        name=controller.name
        if name not in _running_threads:
            raise threadprop.NoControllerThreadError("thread with name {} doesn't exist".format(name))
        del _running_threads[name]
    _running_threads_notifier.notify()
def get_controller(name=None, wait=True, timeout=None):
    if name is None:
        return threadprop.current_controller()
    ctd=general.Countdown(timeout)
    cnt=0
    while True:
        with _running_threads_lock:
            if name not in _running_threads:
                if not wait:
                    raise threadprop.NoControllerThreadError("thread with name {} doesn't exist".format(name))
            else:
                return _running_threads[name]
        cnt=_running_threads_notifier.wait(cnt,timeout=ctd.time_left())
        # print cnt
def stop_controller(name, sync=True, require_controller=False):
    try:
        controller=get_controller(name,wait=False)
        controller.stop()
        if sync:
            controller.sync_exec("stop")
    except threadprop.NoControllerThreadError:
        if require_controller:
            raise
def stop_all_controllers(sync=True):
    global _running_threads_stopping
    with _running_threads_lock:
        _running_threads_stopping=True
        names=_running_threads.values()
    for n in names:
        stop_controller(n)