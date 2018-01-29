from ...core.gui.qt.thread import controller,threadprop
from ...core.utils import general, dictionary


from PyQt4 import QtCore

_controller_uids=general.NamedUIDGenerator(thread_safe=True)

class GuiController(object):

    def __init__(self, name=None):
        object.__init__(self)
        self.name=name or _controller_uids(type(self).__name__)
        self._parameter_nodes={}
        self._parameter_nodes_order=[]
        self._signal_pool_uids=[]
        self.current_controller().on_start

    def setup_gui(self):
        pass
    def cleanup_gui(self):
        pass

    def on_start(self):
        pass
    def on_finish(self):
        for uid in self._signal_pool_uids:
            threadprop.current_controller().unsubscribe(uid)

    def send_signal(self, tag, value, dst=None, src=None):
        src=src or self.name
        threadprop.current_controller().send_signal(tag,value,dst=dst,src=self.name)
    def subscribe(self, callback, srcs=None, tags=None, filt=None, dsts="__self__", priority=0, limit_queue=1, limit_period=0, id=None):
        uid=threadprop.current_controller().subscribe(callback,srcs=srcs,dsts=dsts,tags=tags,filt=filt,priority=priority,
                limit_queue=limit_queue,limit_period=limit_period,dest_controller=self,id=id)
        self._signal_pool_uids.append(uid)
        return uid
    def unsubscribe(self, id):
        self._signal_pool_uids.pop(id)
        threadprop.current_controller().unsubscribe(id)
        
    def _add_parameter_node(self, path, getter=None, setter=None):
        """
        Adds a parameter.
        
        `getter`/`setter` are methods for getting/setting this parameter.
        Can be ``None``, meaning that this parameter is ingored when executing :func:`get_parameter`/:func:`apply_parameter`.
        """
        self._parameter_nodes[path]=(getter,setter)
        self._parameter_nodes_order.append(path)
    def get_parameters(self):
        """Get Dictionary ``{name: value}`` containing all the gui parameter."""
        parameter=dictionary.Dictionary()
        for k in self._parameter_nodes_order:
            g,_=self._parameter_nodes[k]
            if g:
                parameter[k]=g()
        return parameter
    def apply_parameters(self, parameters):
        """
        Apply the parameters.
        
        `parameter` is the dict ``{name: value}`` of the gui available parameter.
        Non-applicable parameter are ignored.
        """
        for k in self._parameter_nodes_order:
            _,s=self._parameter_nodes[k]
            if s and (k in parameters):
                s(parameters[k])
    def __getitem__(self, key):
        """Get the value of a parameter parameter."""
        if key in self._parameter_nodes:
            g=self._parameter_nodes[key][0]
            if g:
                return g()
            raise ValueError("no getter for value '{}'".format(key))
        raise KeyError("no property '{}'".format(key))
    def __setitem__(self, key, value):
        """Set the value of a parameter parameter."""
        if key in self._parameter_nodes:
            s=self._parameter_nodes[key][1]
            if s:
                return s(value)
            raise ValueError("no setter for value '{}'".format(key))
        raise KeyError("no property '{}'".format(key))