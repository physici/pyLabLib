from . import thread
from ...thread import threadprop, message_queue
from ...utils import observer_pool, py3, general

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

    ObserverAttr=collections.namedtuple("ObserverAttr",["callback_controller","sync","is_gui","is_msg"])
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
        callback_controller=threadprop.current_controller()
        is_gui=thread.is_gui_thread()
        is_msg=isinstance(callback,py3.textstring)
        attr=self.ObserverAttr(callback_controller,sync,is_gui,is_msg)
        return self._pool.add_observer(callback,name=id,filt=full_filt,priority=priority,attr=attr)
    def unsubscribe(self, id):
        self._pool.remove_observer(id)

    @staticmethod
    def _call_observer(ctl, obs, args):
        callback=obs.callback
        callback_controller=obs.attr.callback_controller
        if obs.attr.is_msg:
            message_queue.send_message(callback_controller,callback,args)
        else:
            if callback_controller is ctl:
                return callback(*args)
            elif obs.is_gui:
                thread.call_after(callback,args)
            else:
                return callback_controller.call_from_thread(callback,args,sync_done=obs.attr.sync)
    @staticmethod
    @thread.gui_func_sync
    def _call_gui_observers_sync(to_call, args):
        return [(n,obs.callback(*args)) for n,obs in to_call]
    def signal(self, src, tag, value, dst=None):
        to_call=self._pool.find_observers((src,dst,tag))
        args=(src,tag,value)
        gui_call,non_gui_call=general.partition_list(lambda o: (o[1].attr.is_gui and o[1].attr.sync and not o[1].attr.is_msg), to_call)
        ctl=threadprop.current_controller()
        gui_results=self._call_gui_observers_sync(gui_call,args)
        non_gui_results=[(name,self._call_observer(ctl,obs,args)) for name,obs in non_gui_call]
        return dict(gui_results+non_gui_results)