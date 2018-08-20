from ....utils import general, funcargparse, dictionary, functions as func_utils
from . import signal_pool, threadprop, synchronizing

from PyQt5 import QtCore

import threading
import time
import sys, traceback
    
_depends_local=["....mthread.notifier"]

_default_signal_pool=signal_pool.SignalPool()

_created_threads={}
_running_threads={}
_stopped_threads={}
_running_threads_lock=threading.Lock()
_running_threads_notifier=synchronizing.QMultiThreadNotifier()
_running_threads_stopping=False


def exsafe(func):
    """Decorator that intercepts exceptions raised by `func` and stops the execution in a controlled manner (quitting the main thread)"""
    @func_utils.getargsfrom(func,overwrite={'name','varg_name','kwarg_name','doc'})
    def safe_func(*args, **kwargs):
        try:
            return func(*args,**kwargs)
        except:
            traceback.print_exc()
            try:
                stop_controller("gui",code=1,sync=False)
            except threadprop.NoControllerThreadError:
                print("Can't stop GUI thread; quitting the application")
                sys.stdout.flush()
                sys.exit(1)
    return safe_func
def exsafeSlot(*slargs, **slkwargs):
    """Wrapper around :func:`PyQt5.QtCore.pyqtSlot` which intercepts exceptions and stops the execution in a controlled manner"""
    def wrapper(func):
        return QtCore.pyqtSlot(*slargs,**slkwargs)(exsafe(func))
    return wrapper

class QThreadControllerThread(QtCore.QThread):
    finalized=QtCore.pyqtSignal()
    _stop_request=QtCore.pyqtSignal()
    def __init__(self, controller):
        QtCore.QThread.__init__(self)
        self.moveToThread(self)
        self.controller=controller
        threadprop.get_app().aboutToQuit.connect(self.quit_sync)
        self._stop_request.connect(self._do_quit)
    def run(self):
        try:
            self.exec_()
        finally:
            self.finalized.emit()
    @QtCore.pyqtSlot()
    def _do_quit(self):
        if self.isRunning():
            self.quit() # stop event lopp
            self.controller.request_stop() # signal controller to stop
    def quit_sync(self):
        self._stop_request.emit()


def remote_call(func):
    @func_utils.getargsfrom(func,overwrite={'name','varg_name','kwarg_name','doc'})
    def rem_func(self, *args, **kwargs):
        return self.call_in_thread_sync(func,args=(self,)+args,kwargs=kwargs,sync=True,same_thread_shortcut=True)
    return rem_func

def call_in_thread(thread_name):
    def wrapper(func):
        @func_utils.getargsfrom(func,overwrite={'name','varg_name','kwarg_name','doc'})
        def rem_func(*args, **kwargs):
            thread=get_controller(thread_name)
            return thread.call_in_thread_sync(func,args=args,kwargs=kwargs,sync=True,same_thread_shortcut=True)
        return rem_func
    return wrapper
call_in_gui_thread=call_in_thread("gui")

class QThreadController(QtCore.QObject):
    def __init__(self, name=None, kind="loop", signal_pool=None):
        QtCore.QObject.__init__(self)
        funcargparse.check_parameter_range(kind,"kind",{"loop","run","main"})
        if kind=="main":
            name="gui"
        self.name=name or threadprop.thread_uids(type(self).__name__)
        self.kind=kind
        store_created_controller(self)
        if self.kind=="main":
            if not threadprop.is_gui_thread():
                raise threadprop.ThreadError("GUI thread controller can only be created in the main thread")
            if threadprop.current_controller(require_controller=False):
                raise threadprop.DuplicateControllerThreadError()
            self.thread=threadprop.get_gui_thread()
            threadprop.local_data.controller=self
            register_controller(self)
        else:
            self.thread=QThreadControllerThread(self)

        self._wait_timer=QtCore.QBasicTimer()
        self._message_queue={}
        self._sync_queue={}
        self._sync_clearance=set()
        self._exec_notes={}
        self._exec_notes_lock=threading.Lock()
        self._signal_pool=signal_pool or _default_signal_pool
        self._signal_pool_uids=[]
        self._stop_requested=(self.kind!="main")
        self._running=not self._stop_requested
        self.moveToThread(self.thread)
        self.messaged.connect(self._get_message)
        self.interrupt_called.connect(self._on_call_in_thread)
        if self.kind=="main":
            threadprop.get_app().aboutToQuit.connect(self._on_finish_event)
            threadprop.get_app().lastWindowClosed.connect(self._on_last_window_closed)
            self._recv_started_event.connect(self._on_start_event,type=QtCore.Qt.QueuedConnection)
            self._recv_started_event.emit()
        else:
            self.thread.started.connect(self._on_start_event)
            self.thread.finalized.connect(self._on_finish_event)
    
    messaged=QtCore.pyqtSignal("PyQt_PyObject")
    @exsafeSlot("PyQt_PyObject")
    def _get_message(self, msg):
        kind,tag,value=msg
        if kind=="msg":
            if tag.startswith("interrupt."):
                self.process_interrupt(tag[len("interrupt."):],value)
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
            self._stop_requested=True
    interrupt_called=QtCore.pyqtSignal("PyQt_PyObject")
    @exsafeSlot("PyQt_PyObject")
    def _on_call_in_thread(self, call):
        call()

    _recv_started_event=QtCore.pyqtSignal()
    started=QtCore.pyqtSignal()
    @exsafeSlot()
    def _on_start_event(self):
        self._stop_requested=False
        try:
            if self.kind!="main":
                threadprop.local_data.controller=self
                register_controller(self)
            self.notify_exec("start")
            self._running=True
            self.on_start()
            self.started.emit()
            self.notify_exec("run")
            if self.kind=="run":
                self._do_run()
                self.thread.quit_sync()
        except threadprop.InterruptExceptionStop:
            self.thread.quit_sync()
    finished=QtCore.pyqtSignal()
    @exsafeSlot()
    def _on_finish_event(self):
        is_stopped=self._stop_requested
        self._stop_requested=False
        self.finished.emit()
        try:
            self.check_messages()
            self.on_finish()
        finally:
            self._running=False
            for uid in self._signal_pool_uids:
                self._signal_pool.unsubscribe(uid)
            self.notify_exec("stop")
            unregister_controller(self)
            if self.kind=="main":
                stop_all_controllers()
            self._stop_requested=is_stopped
    @QtCore.pyqtSlot()
    def _on_last_window_closed(self):
        if threadprop.get_app().quitOnLastWindowClosed():
            self.request_stop()
    

    def is_controlled(self):
        return QtCore.QThread.currentThread() is self.thread

    def process_interrupt(self, tag, value):
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
    def _wait_in_process_loop(self, done_check, timeout=None):
        ctd=general.Countdown(timeout)
        while True:
            if self._stop_requested:
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
            done,value=done_check()
            if done:
                return value
    def wait_for_message(self, tag, timeout=None):
        def done_check():
            if self._message_queue.setdefault(tag,[]):
                value=self._message_queue[tag].pop(0)
                return True,value
            return False,None
        return self._wait_in_process_loop(done_check,timeout=timeout)
    def new_messages_number(self, tag):
        return len(self._message_queue.setdefault(tag,[]))
    def pop_message(self, tag):
        if self.new_messages_number(tag):
            return self._message_queue[tag].pop(0)
        raise threadprop.NoMessageThreadError("no messages with tag '{}'".format(tag))
    def wait_for_sync(self, tag, uid, timeout=None):
        def done_check():
            if uid in self._sync_queue.setdefault(tag,set()):
                self._sync_queue[tag].remove(uid)
                return True,None
            return False,None
        try:
            self._wait_in_process_loop(done_check,timeout=timeout)
        except threadprop.TimeoutThreadError:
            self._sync_clearance.add((tag,uid))
            raise
    def wait_for_any_message(self, timeout=None):
        self._wait_in_process_loop(lambda: (True,None),timeout=timeout)
    def wait_until(self, check, timeout=None):
        self._wait_in_process_loop(lambda: (check(),None),timeout=timeout)
    def check_messages(self):
        threadprop.get_app().processEvents(QtCore.QEventLoop.AllEvents)
        if self._stop_requested:
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
    def request_stop(self):
        self.messaged.emit(("stop",None,None))
    def stop(self, code=0):
        if self.kind=="main":
            self.call_in_thread_callback(lambda: threadprop.get_app().exit(code))
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
                p=next(gen)
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



class QTaskThread(QMultiRepeatingThreadController):
    def __init__(self, name=None, setupargs=None, setupkwargs=None, signal_pool=None):
        QMultiRepeatingThreadController.__init__(self,name=name,signal_pool=signal_pool)
        self.setupargs=setupargs or []
        self.setupkwargs=setupkwargs or {}
        self._params_val=dictionary.Dictionary()
        self._params_val_lock=threading.Lock()
        self._params_exp=dictionary.Dictionary()
        self._params_exp_lock=threading.Lock()
        self._directed_signal.connect(self._on_directed_signal)
        self._commands={}
        self.c=self.CommandAccess(self,sync=False)
        self.q=self.CommandAccess(self,sync=True)

    def setup_task(self, *args, **kwargs):
        pass
    def process_signal(self, src, tag, value):
        pass
    def process_command(self, *args, **kwargs):
        self.process_named_command(*args,**kwargs)
    def process_query(self, *args, **kwargs):
        self.process_named_command(*args,**kwargs)
    def process_interrupt(self, *args, **kwargs):
        pass
    def finalize_task(self):
        pass

    def on_start(self):
        QMultiRepeatingThreadController.on_start(self)
        self.setup_task(*self.setupargs,**self.setupkwargs)
        self.subscribe_nonsync(self._recv_directed_signal)
    def on_finish(self):
        QMultiRepeatingThreadController.on_finish(self)
        self.finalize_task()

    _directed_signal=QtCore.pyqtSignal("PyQt_PyObject")
    @exsafeSlot("PyQt_PyObject")
    def _on_directed_signal(self, msg):
        self.process_signal(*msg)
    def _recv_directed_signal(self, tag, src, value):
        self._directed_signal.emit((tag,src,value))

    def process_named_command(self, name, *args, **kwargs):
        if name in self._commands:
            self._commands[name](*args,**kwargs)
        else:
            raise KeyError("unrecognized command {}".format(name))

    _variable_change_tag="#sync.wait.variable"
    def set_variable(self, name, value, notify=False, notify_tag="changed/*"):
        with self._params_val_lock:
            self._params_val.add_entry(name,value,force=True)
        for ctl in self._params_exp.get(name,[]):
            ctl.send_message(self._variable_change_tag,value)
        if notify:
            notify_tag.replace("*",name)
            self.send_signal("any",notify_tag,value)
    def __setitem__(self, name, value):
        self.set_variable(name,value)
    def __delitem__(self, name):
        with self._params_val_lock:
            if name in self._params_val:
                del self._params_val[name]
    def add_command(self, name, command=None):
        if name in self._commands:
            raise ValueError("command {} already exists".format(name))
        if command is None:
            command=name
        self._commands[name]=command

    def _sync_call(self, func, args, kwargs, sync, timeout=None):
        return self.call_in_thread_sync(func,args=args,kwargs=kwargs,sync=sync,timeout=timeout,tag="control.execute")
    def command(self, *args, **kwargs):
        self._sync_call(self.process_command,args,kwargs,sync=False)
    def query(self, *args, **kwargs):
        timeout=kwargs.pop("timeout",None)
        return self._sync_call(self.process_query,args,kwargs,sync=True,timeout=timeout)
    def interrupt(self, *args, **kwargs):
        return self.call_in_thread_sync(self.process_interrupt,args,kwargs,sync=False)
    def get_variable(self, name, default=None, copy_branch=True, missing_error=False):
        with self._params_val_lock:
            if missing_error and name not in self._params_val:
                raise KeyError("no parameter {}".format(name))
            var=self._params_val.get(name,default)
            if copy_branch and dictionary.is_dictionary(var):
                var=var.copy()
        return var
    def __getitem__(self, name):
        return self.get_variable(name,missing_error=True)
    def wait_for_variable(self, name, pred, timeout=None):
        if not hasattr(pred,"__call__"):
            v=pred
            pred=lambda x: x==v
        ctl=threadprop.current_controller()
        with self._params_exp_lock:
            self._params_exp.setdefault(name,[]).append(ctl)
        ctd=general.Countdown(timeout)
        try:
            while True:
                value=self.get_variable(name)
                if pred(value):
                    return value
                ctl.wait_for_message(self._variable_change_tag,timeout=ctd.time_left())
        finally:
            with self._params_exp_lock:
                self._params_exp[name].remove(ctl)

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
                def remcall(*args, **kwargs):
                    if self.sync:
                        return parent.query(name,*args,timeout=self.timeout,**kwargs)
                    else:
                        return parent.command(name,*args,**kwargs)
                self._calls[name]=remcall
            return self._calls[name]




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
        _stopped_threads[name]=controller
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
            if name in _stopped_threads:
                raise threadprop.NoControllerThreadError("thread with name {} is stopped".format(name))
        cnt=_running_threads_notifier.wait(cnt,timeout=ctd.time_left())

def stop_controller(name=None, code=0, sync=True, require_controller=False):
    try:
        controller=get_controller(name,wait=False)
        controller.stop(code=code)
        if sync:
            controller.sync_exec("stop")
        return controller
    except threadprop.NoControllerThreadError:
        if require_controller:
            raise
def stop_all_controllers(sync=True, concurrent=True):
    global _running_threads_stopping
    with _running_threads_lock:
        _running_threads_stopping=True
        names=list(_running_threads.keys())
    if concurrent and sync:
        current_ctl=get_controller().name
        ctls=[]
        for n in names:
            if n!=current_ctl:
                ctls.append(stop_controller(n,sync=False))
        for ctl in ctls:
            if ctl:
                ctl.sync_exec("stop")
        stop_controller(current_ctl,sync=True)
    else:
        for n in names:
            stop_controller(n,sync=sync)