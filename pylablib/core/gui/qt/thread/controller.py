from ....utils import general, funcargparse, dictionary, functions as func_utils
from . import signal_pool, threadprop, synchronizing

from PyQt5 import QtCore

import threading
import time
import sys, traceback
import heapq
    
_depends_local=["....mthread.notifier"]

_default_signal_pool=signal_pool.SignalPool()

_created_threads={}
_running_threads={}
_stopped_threads={}
_running_threads_lock=threading.Lock()
_running_threads_notifier=synchronizing.QMultiThreadNotifier()
_running_threads_stopping=False


_exception_print_lock=threading.Lock()

def exsafe(func):
    """Decorator that intercepts exceptions raised by `func` and stops the execution in a controlled manner (quitting the main thread)"""
    @func_utils.getargsfrom(func,overwrite={'name','varg_name','kwarg_name','doc'})
    def safe_func(*args, **kwargs):
        try:
            return func(*args,**kwargs)
        except threadprop.InterruptExceptionStop:
            pass
        except:
            with _exception_print_lock:
                try:
                    ctl_name=get_controller(wait=False).name
                    print("Exception raised in thread '{}' executing function '{}':".format(ctl_name,func.__name__))
                except threadprop.NoControllerThreadError:
                    print("Exception raised in uncontroled thread executing function '{}':".format(func.__name__))
                traceback.print_exc()
                sys.stdout.flush()
            try:
                stop_controller("gui",code=1,sync=False,require_controller=True)
            except threadprop.NoControllerThreadError:
                with _exception_print_lock:
                    print("Can't stop GUI thread; quitting the application")
                    sys.stdout.flush()
                sys.exit(1)
            except threadprop.InterruptExceptionStop:
                pass
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
        self._stop_requested=False
    def run(self):
        try:
            self.exec_() # main execution event loop
        finally:
            self.finalized.emit()
            self.exec_() # finalizing event loop (exitted after finalizing event is processed)
    @QtCore.pyqtSlot()
    def _do_quit(self):
        if self.isRunning() and not self._stop_requested:
            self.controller.request_stop() # signal controller to stop
            self.quit() # quit the first event lopp
            self._stop_requested=True
    def quit_sync(self):
        self._stop_request.emit()


def remote_call(func):
    """Decorator that turns a controller method into a remote call (call from a different thread is passed synchronously)"""
    @func_utils.getargsfrom(func,overwrite={'name','varg_name','kwarg_name','doc'})
    def rem_func(self, *args, **kwargs):
        return self.call_in_thread_sync(func,args=(self,)+args,kwargs=kwargs,sync=True,same_thread_shortcut=True)
    return rem_func

def call_in_thread(thread_name):
    """Decorator that turns any function into a remote call in a thread with a given name (call from a different thread is passed synchronously)"""
    def wrapper(func):
        @func_utils.getargsfrom(func,overwrite={'name','varg_name','kwarg_name','doc'})
        def rem_func(*args, **kwargs):
            thread=get_controller(thread_name)
            return thread.call_in_thread_sync(func,args=args,kwargs=kwargs,sync=True,same_thread_shortcut=True)
        return rem_func
    return wrapper
call_in_gui_thread=call_in_thread("gui")
"""Decorator that turns any function into a remote call in a GUI thread (call from a different thread is passed synchronously)"""




class QThreadController(QtCore.QObject):
    def __init__(self, name=None, kind="loop", signal_pool=None):
        QtCore.QObject.__init__(self)
        funcargparse.check_parameter_range(kind,"kind",{"loop","run","main"})
        if kind=="main":
            name="gui"
        self.name=name or threadprop.thread_uids(type(self).__name__)
        self.kind=kind
        # register thread
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

        # set up message processing
        self._wait_timer=QtCore.QBasicTimer()
        self._message_queue={}
        self._message_uid=0
        self._sync_queue={}
        self._sync_clearance=set()
        # set up high-level synchrnoization
        self._exec_notes={}
        self._exec_notes_lock=threading.Lock()
        self._signal_pool=signal_pool or _default_signal_pool
        self._signal_pool_uids=[]
        # set up life control
        self._stop_requested=(self.kind!="main")
        self._running=not self._stop_requested
        # set up signals
        self.moveToThread(self.thread)
        self._messaged.connect(self._get_message)
        self._interrupt_called.connect(self._on_call_in_thread,QtCore.Qt.QueuedConnection)
        if self.kind=="main":
            threadprop.get_app().aboutToQuit.connect(self._on_finish_event,type=QtCore.Qt.DirectConnection)
            threadprop.get_app().lastWindowClosed.connect(self._on_last_window_closed,type=QtCore.Qt.DirectConnection)
            self._recv_started_event.connect(self._on_start_event,type=QtCore.Qt.QueuedConnection) # invoke delayed start event (call in the main loop)
            self._recv_started_event.emit()
        else:
            self.thread.started.connect(self._on_start_event,type=QtCore.Qt.QueuedConnection)
            self.thread.finalized.connect(self._on_finish_event,type=QtCore.Qt.QueuedConnection)
    
    ### Special signals processing ###
    _messaged=QtCore.pyqtSignal("PyQt_PyObject")
    @exsafeSlot("PyQt_PyObject")
    def _get_message(self, msg): # message signal processing
        kind,tag,priority,value=msg
        if kind=="msg":
            if tag.startswith("interrupt."):
                self.process_interrupt(tag[len("interrupt."):],value)
                return
            if self.process_message(tag,value):
                return
            mq=self._message_queue.setdefault(tag,[])
            heapq.heappush(mq,(priority,self._message_uid,value))
            self._message_uid+=1
        elif kind=="sync":
            if (tag,value) in self._sync_clearance:
                self._sync_clearance.remove((tag,value))
            else:
                self._sync_queue.setdefault(tag,set()).add(value)
        elif kind=="stop":
            self._stop_requested=True
    _interrupt_called=QtCore.pyqtSignal("PyQt_PyObject")
    @exsafeSlot("PyQt_PyObject")
    def _on_call_in_thread(self, call): # call signal processing
        call()

    ### Execution starting / finishing ###
    _recv_started_event=QtCore.pyqtSignal()
    started=QtCore.pyqtSignal()
    @exsafeSlot()
    def _on_start_event(self):
        self._stop_requested=False
        try:
            if self.kind!="main":
                threadprop.local_data.controller=self
                register_controller(self)
            self._running=True
            self.notify_exec("start")
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
            self.check_messages()
        finally:
            self._running=False
            for uid in self._signal_pool_uids:
                self._signal_pool.unsubscribe(uid)
            if self.kind=="main":
                stop_all_controllers(stop_self=False)
            self.notify_exec("stop")
            unregister_controller(self)
            self._stop_requested=is_stopped
            self.thread.quit() # stop event loop (no regular messages processed after this call, although loop is run manually in the thread finalizing procedure)
    @QtCore.pyqtSlot()
    def _on_last_window_closed(self):
        if threadprop.get_app().quitOnLastWindowClosed():
            self.request_stop()



    ##########  INTERNAL CALLS  ##########
    ## Methods to be called by functions executing in the controlled thread ##

    ### Message loop management ###
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
        """
        Wait for a single message with a given tag.

        If timeout is passed, raise :exc:`threadprop.TimeoutThreadError`.
        """
        def done_check():
            if self._message_queue.setdefault(tag,[]):
                value=heapq.heappop(self._message_queue[tag])[-1]
                return True,value
            return False,None
        return self._wait_in_process_loop(done_check,timeout=timeout)
    def new_messages_number(self, tag):
        """
        Get the number of queued messages with a given tag.
        """
        return len(self._message_queue.setdefault(tag,[]))
    def pop_message(self, tag):
        """
        Pop the latest message with the given tag.

        Select the message with the highest priority, and among those the oldest one.
        If no messages are available, raise :exc:`threadprop.NoMessageThreadError`.
        """
        if self.new_messages_number(tag):
            return heapq.heappop(self._message_queue[tag])[-1]
        raise threadprop.NoMessageThreadError("no messages with tag '{}'".format(tag))
    def wait_for_sync(self, tag, uid, timeout=None):
        """
        Wait for synchronization signal with the given tag and UID.

        This method is rarely invoked directly, and is usually used by synchronizers code.
        If timeout is passed, raise :exc:`threadprop.TimeoutThreadError`.
        """
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
        """
        Wait for any message (including synchronization messages or pokes).

        If timeout is passed, raise :exc:`threadprop.TimeoutThreadError`.
        """
        self._wait_in_process_loop(lambda: (True,None),timeout=timeout)
    def wait_until(self, check, timeout=None):
        """
        Wait until a given condition is true.

        Condition is given by the `check` function, which is called after every new received message and should return ``True`` if the condition is met.
        If timeout is passed, raise :exc:`threadprop.TimeoutThreadError`.
        """
        self._wait_in_process_loop(lambda: (check(),None),timeout=timeout)
    def check_messages(self):
        """
        Receive new messages.

        Runs the underlying message loop to process newely received message and signals (and place them in corresponding queues if necessary).
        This method is rarely invoked, and only should be used periodically during long computations to not 'freeze' the thread.
        """
        threadprop.get_app().processEvents(QtCore.QEventLoop.AllEvents)
        if self._stop_requested:
            raise threadprop.InterruptExceptionStop()
    def sleep(self, timeout):
        """
        Sleep for a given time (in seconds).

        Unlike :func:`time.sleep`, constantly checks the event loop for new messages (e.g., if stop or interrup commands are issued).
        """
        try:
            self._wait_in_process_loop(lambda: (False,None),timeout=timeout)
        except threadprop.TimeoutThreadError:
            pass


    ### Overloaded methods for thread events ###
    def process_interrupt(self, tag, value):
        if tag=="execute":
            value()
    def process_message(self, tag, value):
        """
        Process a new message.

        If the function returns ``False``, the message is put in the corresponding queue.
        Otherwise, the the message is considered to be already, and it gets 'absorbed'.
        """
        return False
    def on_start(self):
        """Method invoked on the start of the thread."""
        pass
    def on_finish(self):
        """
        Method invoked in the end of the thread.
        
        Called regardless of the stopping reason (normal finishing, exception, application finishing).
        """
        pass
    def run(self):
        """Method called to run the main thread code (only for ``"run"`` thread kind)."""
        pass


    ### Managing signal pool interaction ###
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
    def send_signal(self, dst="any", tag=None, value=None, src=None):
        self._signal_pool.signal(src or self.name,dst,tag,value)



    ##########  EXTERNAL CALLS  ##########
    ## Methods to be called by functions executing in other thread ##

    ### Message synchronization ###
    def send_message(self, tag, value, priority=0):
        """Send a message to the thread with a given tag, value and priority"""
        self._messaged.emit(("msg",tag,priority,value))
    def send_sync(self, tag, uid):
        """
        Send a synchronization signal with the given tag and UID.

        This method is rarely invoked directly, and is usually used by synchronizers code.
        """
        self._messaged.emit(("sync",tag,0,uid))

    ### Thread exection control ###
    def start(self):
        """Start the thread."""
        self.thread.start()
    def request_stop(self):
        """Request thread stop (send a stop command)."""
        self._messaged.emit(("stop",None,0,None))
    def stop(self, code=0):
        """
        Stop the thread.

        If called from the thread, stop immediately by raising a :exc:`InterruptExceptionStop` exception. Otherwise, schedule thread stop.
        If the thread kind is ``"main"``, stop the whole application with the given exit code. Otherwise, stop the thread.
        """
        if self.kind=="main":
            def exit_main():
                threadprop.get_app().exit(code)
                self.request_stop()
            self.call_in_thread_callback(exit_main)
        else:
            self.thread.quit_sync()
        if threadprop.current_controller() is self:
            raise threadprop.InterruptExceptionStop
    def poke(self):
        """
        Send a dummy message to the thread.
        
        A cheap way to notify the thread that something happened (useful for, e.g., making thread leave :meth:`wait_for_any_message` method).
        """
        self._messaged.emit(("poke",None,0,None))
    def running(self):
        """Check if the thread is running."""
        return self._running
    

    def is_controlled(self):
        """Check if this controller corresponds to the current thread."""
        return QtCore.QThread.currentThread() is self.thread
    
    def _get_exec_note(self, point):
        with self._exec_notes_lock:
            if point not in self._exec_notes:
                self._exec_notes[point]=synchronizing.QMultiThreadNotifier()
            return self._exec_notes[point]
    def notify_exec(self, point):
        """
        Mark the given execution point as passed.
        
        Automatically invoked points include ``"start"`` (thread starting), ``"run"`` (thread setup and ready to run), and ``"stop"`` (thread finished),
        but can be extended for arbitrary points.
        Any given point can be notified only once, the repeated notification causes error.
        """
        self._get_exec_note(point).notify()
    def sync_exec(self, point, timeout=None):
        """
        Wait for the given execution point.
        
        Automatically invoked points include ``"start"`` (thread starting), ``"run"`` (thread setup and ready to run), and ``"stop"`` (thread finished).
        If timeout is passed, raise :exc:`threadprop.TimeoutThreadError`.
        """
        return self._get_exec_note(point).wait(timeout=timeout)

    def call_in_thread_callback(self, func, args=None, kwargs=None, callback=None, tag=None, priority=0):
        """
        Call a function in this thread with the given arguments.

        If `callback` is supplied, call it with the result as a single argument (call happens in the controller thread).
        If `tag` is supplied, send the call in a message with the given tag; otherwise, use the interrupt call (generally, higher priority method).
        """
        def call():
            res=func(*(args or []),**(kwargs or {}))
            if callback:
                callback(res)
        if tag is None:
            self._interrupt_called.emit(call)
        else:
            self.send_message(tag,call,priority=priority)
    def call_in_thread_sync(self, func, args=None, kwargs=None, sync=True, timeout=None, default_result=None, pass_exception=True, tag=None, priority=0, same_thread_shortcut=True):
        """
        Call a function in this thread with the given arguments.

        If ``sync==True``, calling thread is blocked until the controlled thread executes the function, and the function result is returned
        (in essence, the fact that the function executes in a different thread is transparent).
        Otherwise, exit call immediately, and return a synchronizer object which can be used to check if the call is done and obtain the result.
        If ``pass_exception==True`` and `func` raises and exception, re-raise it in the caller thread (applies only if ``sync==True``).
        If `tag` is supplied, send the call in a message with the given tag and priority; otherwise, use the interrupt call (generally, higher priority method).
        If `same_thread_shortcut==True`` (default), the call is synchronous, and the caller thread is the same as the controlled thread, call the function directly.
        """
        if same_thread_shortcut and sync and threadprop.current_controller() is self:
            return func(*(args or []),**(kwargs or {}))
        call=synchronizing.QSyncCall(func,args=args,kwargs=kwargs,pass_exception=pass_exception)
        if tag is None:
            self._interrupt_called.emit(call)
        else:
            self.send_message(tag,call,priority=priority)
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
        self.add_job(name,do_step,period,initial_call=False)
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
        name=None
        left=None
        for n in self._jobs_list:
            t=self.timers[n]
            l=t.time_left(ct)
            if l==0:
                name,left=n,0
                break
            elif (left is None) or (l<left):
                name,left=n,l
        return name,left
    def _acknowledge_job(self, name):
        try:
            idx=self._jobs_list.index(name)
            self._jobs_list.pop(idx)
            self._jobs_list.append(name)
            self.timers[name].acknowledge(nmin=1)
        except ValueError:
            pass
    def check_commands(self):
        while self.new_messages_number("control.execute"):
            call=self.pop_message("control.execute")
            call()
    
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
                run_job=True
                if (self._last_sync_time is None) or (self._last_sync_time+self.sync_period<=ct):
                    self._last_sync_time=ct
                    if not to:
                        self.check_messages()
                if to:
                    if to>self._new_jobs_check_period:
                        run_job=False
                        self.sleep(self._new_jobs_check_period)
                    else:
                        self.sleep(to)
                if run_job:
                    self._acknowledge_job(name)
                    job=self.jobs[name]
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
        self._command_priorities={}
        self.c=self.CommandAccess(self,sync=False)
        self.q=self.CommandAccess(self,sync=True)
        self.qs=self.CommandAccess(self,sync=True,safe=True)

    def setup_task(self, *args, **kwargs):
        pass
    def process_signal(self, src, tag, value):
        pass
    def process_command(self, name, *args, **kwargs):
        return self.process_named_command(name,*args,**kwargs)
    def process_query(self, name, *args, **kwargs):
        return self.process_named_command(name,*args,**kwargs)
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
            return self._commands[name](*args,**kwargs)
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
    def add_command(self, name, command=None, priority=0):
        if name in self._commands:
            raise ValueError("command {} already exists".format(name))
        if command is None:
            command=name
        self._commands[name]=command
        self._command_priorities[name]=priority

    def _sync_call(self, func, name, args, kwargs, sync, timeout=None, priority=0):
        priority=self._command_priorities.get(name,0)
        return self.call_in_thread_sync(func,args=(name,)+tuple(args),kwargs=kwargs,sync=sync,timeout=timeout,tag="control.execute",priority=priority)
    def command(self, name, *args, **kwargs):
        self._sync_call(self.process_command,name,args,kwargs,sync=False)
    def query(self, name, *args, **kwargs):
        timeout=kwargs.pop("timeout",None)
        return self._sync_call(self.process_query,name,args,kwargs,sync=True,timeout=timeout)
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
            if isinstance(pred,(tuple,list,set,dict)):
                pred=lambda x: x in v
            else:
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
        def __init__(self, parent, sync, timeout=None, safe=False):
            object.__init__(self)
            self.parent=parent
            self.sync=sync
            self.timeout=timeout
            self.safe=safe
            self._calls={}
        def __getattr__(self, name):
            if name not in self._calls:
                parent=self.parent
                def remcall(*args, **kwargs):
                    if self.sync:
                        return parent.query(name,*args,timeout=self.timeout,**kwargs)
                    else:
                        return parent.command(name,*args,**kwargs)
                if self.safe:
                    remcall=exsafe(remcall)
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
def stop_all_controllers(sync=True, concurrent=True, stop_self=True):
    global _running_threads_stopping
    with _running_threads_lock:
        _running_threads_stopping=True
        names=list(_running_threads.keys())
    current_ctl=get_controller().name
    if concurrent and sync:
        ctls=[]
        for n in names:
            if n!=current_ctl:
                ctls.append(stop_controller(n,sync=False))
        for ctl in ctls:
            if ctl:
                ctl.sync_exec("stop")
    else:
        for n in names:
            if (n!=current_ctl):
                stop_controller(n,sync=sync)
    if stop_self:
        stop_controller(current_ctl,sync=True)