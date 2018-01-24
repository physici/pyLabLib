from ...utils import observer_pool, py3

import collections

def _as_name_list(lst):
    if lst is None:
        return None
    elif isinstance(lst,py3.textstring):
        return [lst]
    return lst
class SignalPool(object):
    def __init__(self):
        object.__init__(self)
        self._pool=observer_pool.ObserverPool()

    ObserverAttr=collections.namedtuple("ObserverAttr",["sync"])
    def subscribe(self, callback, srcs=None, dsts=None, tags=None, filt=None, priority=0, sync=True, id=None):
        srcs=_as_name_list(srcs)
        dsts=_as_name_list(dsts)
        tags=_as_name_list(tags)
        def full_filt(tag):
            src,dst,tag=tag
            if (tags is not None) and (tag is not None) and (tag not in tags):
                return False
            if (srcs is not None) and (src is not None) and (src not in srcs):
                return False
            if (dsts is not None) and (dst is not None) and (dst not in dsts):
                return False
            return filt(src,dst,tag) if (filt is not None) else True
        attr=self.ObserverAttr(sync)
        return self._pool.add_observer(callback,name=id,filt=full_filt,priority=priority,attr=attr)
    def unsubscribe(self, id):
        self._pool.remove_observer(id)

    def signal(self, src, tag, value, dst=None):
        to_call=self._pool.find_observers((src,dst,tag))
        return [(name,obs.callback(src,tag,value)) for name,obs in to_call]