from ....utils import observer_pool, py3
from . import threadprop

import threading
import collections
import time


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
    def _call_done(self):
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


def _as_name_list(lst):
    if lst is None:
        return None
    elif isinstance(lst,py3.textstring):
        return [lst]
    return lst
Signal=collections.namedtuple("Signal",["src","tag","value"])
class SignalPool(object):
    def __init__(self):
        object.__init__(self)
        self._pool=observer_pool.ObserverPool()

    def subscribe_nonsync(self, callback, srcs="any", dsts="any", tags=None, filt=None, priority=0, id=None):
        srcs=_as_name_list(srcs)
        dsts=_as_name_list(dsts)
        tags=_as_name_list(tags)
        src_any="any" in srcs
        dst_any="any" in dsts
        def full_filt(tag, value):
            src,dst,tag=tag
            if (tags is not None) and (tag is not None) and (tag not in tags):
                return False
            if (not src_any) and (src!="all") and (src not in srcs):
                return False
            if (not dst_any) and (dst!="all") and (dst not in dsts):
                return False
            return filt(src,dst,tag,value) if (filt is not None) else True
        return self._pool.add_observer(callback,name=id,filt=full_filt,priority=priority,cacheable=(filt is None))
    def subscribe(self, callback, srcs="any", dsts="any", tags=None, filt=None, priority=0, limit_queue=1, limit_period=0, dest_controller=None, id=None):
        sync_callback=SignalSynchronizer(callback,limit_queue=limit_queue,limit_period=limit_period,dest_controller=dest_controller)
        return self.subscribe_nonsync(sync_callback,srcs=srcs,dsts=dsts,tags=tags,filt=filt,priority=priority,id=id)
    def unsubscribe(self, id):
        self._pool.remove_observer(id)

    def signal(self, src, dst, tag, value):
        to_call=self._pool.find_observers(Signal(src,dst,tag),value)
        # if len(to_call)>1:
        #     print(src,dst,tag,to_call)
        for _,obs in to_call:
            obs.callback(src,tag,value)