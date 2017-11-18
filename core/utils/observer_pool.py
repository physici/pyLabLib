"""
A simple observer pool (notification pool) implementeation.
"""

import collections
from . import general, funcargparse

_depends_local=[".general"]

class ObserverPool(object):
    """
    An observer pool.

    Stores notification functions (callbacks), and calls them whenever :meth:`notify` is called.
    The callbacks can have priority (higher prioirity ones are called first) and tags (observer is only called if the notifying tag is among its tags).

    Args:
        expand_tuple(bool): if ``True`` and the notification value is a tuple, treat it as an argument list for the callback functions.
    """
    def __init__(self, expand_tuple=True):
        self._observers={}
        self._expand_tuple=expand_tuple
    
    _names_generator=general.NamedUIDGenerator(thread_safe=True)
    Observer=collections.namedtuple("Observer",["tags","callback","priority"])
    def add_observer(self, callback, name=None, tags=None, priority=0):
        """
        Add the observer callback.

        Args:
            callback(callable): callback function; takes at least one argument (notification tag), and possible more depending on the notification value.
            name(str): stored callback name; by default, a unique name is auto-generated
            tags(list or None): list of tags for this obserever (it is called only of the :meth:`notify` function tag is in this list); by default, all tags are accepted
            priority(int): callback priority; higher priority callback are invoked first.
        Returns:
            callback name (equal to `name` if supplied; an automatically generated name otherwise).
        """
        if name is None:
            name=self._names_generator("observer")
        if tags is not None:
            tags=funcargparse.as_sequence(tags,allowed_type="list")
        self._observers[name]=self.Observer(tags,callback,priority)
        return name
    def remove_observer(self, name):
        """Remove the observer callback with the given name."""
        del self._observers[name]
    
    def _call_observer(self, callback, tag, value):
        if self._expand_tuple and isinstance(value,tuple):
            return callback(tag,*value)
        else:
            return callback(tag,value)
    def notify(self, tag, value=()):
        """
        Notify the obserevers by calling their callbacks.

        Return a dictionary of the callback results.
        By default the value is an empty tuple: for ``expand_tuple==True`` this means that only one argument (`tag`) is passed to the cakkbacks.
        """
        to_call=[]
        for n,o in self._observers.items():
            if (o.tags is None) or (tag in o.tags):
                to_call.append((n,o))
        to_call.sort(key=lambda x: x[1].priority)
        results=[(n,self._call_observer(o.callback,tag,value)) for n,o in to_call]
        return dict(results)