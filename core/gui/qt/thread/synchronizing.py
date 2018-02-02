from . import threadprop
from ....mthread import notifier
from ....utils import general

import  threading


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