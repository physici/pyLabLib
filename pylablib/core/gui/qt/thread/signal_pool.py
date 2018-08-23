from ....utils import observer_pool, py3
from . import synchronizing

import collections


def _as_name_list(lst):
    if lst is None:
        return None
    elif isinstance(lst,py3.textstring):
        return [lst]
    return lst
TSignal=collections.namedtuple("TSignal",["src","tag","value"])
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
        sync_callback=synchronizing.SignalSynchronizer(callback,limit_queue=limit_queue,limit_period=limit_period,dest_controller=dest_controller)
        return self.subscribe_nonsync(sync_callback,srcs=srcs,dsts=dsts,tags=tags,filt=filt,priority=priority,id=id)
    def unsubscribe(self, id):
        self._pool.remove_observer(id)

    def signal(self, src, dst="any", tag=None, value=None):
        to_call=self._pool.find_observers(TSignal(src,dst,tag),value)
        for _,obs in to_call:
            obs.callback(src,tag,value)