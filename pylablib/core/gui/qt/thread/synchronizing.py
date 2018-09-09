from . import threadprop
from ....mthread import notifier
from ....utils import general

import threading, time


class QThreadNotifier(notifier.ISkippableNotifier):
    _uid_gen=general.UIDGenerator(thread_safe=True)
    _notify_tag="#sync.notifier"
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
    def get_value_sync(self, timeout=None):
        if not self.done_wait():
            self.wait(timeout=timeout)
        return self.get_value()


class QMultiThreadNotifier(object):
    def __init__(self):
        object.__init__(self)
        self._lock=threading.Lock()
        self._cnt=0
        self._notifiers=[]
    def wait(self, state=1, timeout=None):
        with self._lock:
            if self._cnt>=state:
                return self._cnt+1
            n=QThreadNotifier()
            self._notifiers.append(n)
        success=n.wait(timeout=timeout)
        if success:
            return n.get_value()
        raise threadprop.TimeoutThreadError("synchronizer timed out")
    def notify(self):
        with self._lock:
            self._cnt+=1
            cnt=self._cnt
            notifiers=self._notifiers
            self._notifiers=[]
        for n in notifiers:
            n.notify(cnt)


class QThreadCallNotifier(QThreadNotifier):
    def get_value_sync(self, timeout=None, default=None, error_on_fail=True, pass_exception=True):
        res=QThreadNotifier.get_value_sync(self,timeout=timeout)
        if res:
            kind,value=res
            if kind=="result":
                return value
            elif kind=="exception":
                if pass_exception:
                    raise value
                else:
                    return default
            else:
                if error_on_fail:
                    raise threadprop.ThreadError("failed executing remote call")
                return default
        else:
            if error_on_fail:
                raise threadprop.TimeoutThreadError()
            return default

class QSyncCall(object):
    def __init__(self, func, args=None, kwargs=None, pass_exception=True, error_on_fail=True):
        object.__init__(self)
        self.func=func
        self.args=args or []
        self.kwargs=kwargs or {}
        self.synchronizer=QThreadCallNotifier()
        self.pass_exception=pass_exception
        self.error_on_fail=error_on_fail
    def __call__(self):
        try:
            res=("fail",None)
            res=("result",self.func(*self.args,**self.kwargs))
        except Exception as e:
            res=("exception",e)
            raise
        finally:
            self.synchronizer.notify(res)
    def value(self, sync=True, timeout=None, default=None):
        if sync:
            return self.synchronizer.get_value_sync(timeout=timeout,default=default,error_on_fail=self.error_on_fail,pass_exception=self.pass_exception)
        else:
            return self.synchronizer
    def wait(self, timeout=None):
        return self.synchronizer.wait(timeout)
    def done(self):
        return self.synchronizer.done_wait()




class SignalSynchronizer(object):
    def __init__(self, func, limit_queue=1, limit_period=0, dest_controller=None):
        dest_controller=dest_controller or threadprop.current_controller()
        def call(*args):
            dest_controller.call_in_thread_callback(func,args,callback=self._call_done)
        self.call=call
        self.limit_queue=limit_queue
        self.queue_size=0
        self.limit_period=limit_period
        self.last_call_time=None
        self.lock=threading.Lock()
    def _call_done(self, _):
        with self.lock:
            self.queue_size-=1
            
    def __call__(self, src, tag, value):
        with self.lock:
            if self.limit_queue and self.queue_size>=self.limit_queue:
                return
            if self.limit_period:
                t=time.time()
                if (self.last_call_time is not None) and (self.last_call_time+self.limit_period>t):
                    return
                self.last_call_time=t
            self.queue_size+=1
        self.call(src,tag,value)