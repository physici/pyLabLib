import collections
from . import general, funcargparse

_depends_local=[".general"]

class ObserverPool(object):
    def __init__(self, expand_tuple=True):
        self._observers={}
        self._expand_tuple=expand_tuple
    
    _names_generator=general.NamedUIDGenerator(thread_safe=True)
    Observer=collections.namedtuple("Observer",["tags","callback","priority"])
    def add_observer(self, callback, name=None, tags=None, priority=0):
        if name is None:
            name=self._names_generator("observer")
        if tags is not None:
            tags=funcargparse.as_sequence(tags,allowed_type="list")
        self._observers[name]=self.Observer(tags,callback,priority)
        return name
    def remove_observer(self, name):
        del self._observers[name]
    
    def _call_observer(self, callback, tag, value):
        if self._expand_tuple and isinstance(value,tuple):
            return callback(tag,*value)
        else:
            return callback(tag,value)
    def notify(self, tag, value=None):
        to_call=[]
        for n,o in self._observers.items():
            if (o.tags is None) or (tag in o.tags):
                to_call.append((n,o))
        to_call.sort(key=lambda x: x[1].priority)
        results=[(n,self._call_observer(o.callback,tag,value)) for n,o in to_call]
        return dict(results)