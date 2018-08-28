### Interface for a generic device class ###
 
_info_node_kinds=["settings","status","full_info"]
 
class IDevice(object):
    """
    A base class for an instrument.
     
    Contains some useful functions for dealing with device settings.
    """
    def __init__(self):
        object.__init__(self)
        self._settings_ignore_error={"get":(),"set":()}
        self._info_nodes=dict([(ik,{}) for ik in _info_node_kinds])
        self._info_nodes_order=dict([(ik,[]) for ik in _info_node_kinds])
        self._add_full_info_node("cls",lambda: self.__class__.__name__)
         
    def open(self):
        """Open the connection"""
        pass
    def close(self):
        """Close the connection"""
        pass
    def is_opened(self):
        """Check if the device is connected"""
        return True
    def __bool__(self):
        return self.is_opened()
    def __enter__(self):
        return self
    def __exit__(self, *args, **vargs):
        self.close()
        return False
     
 
    def _add_info_node(self, path, kind, getter=None, setter=None, ignore_error=()):
        """
        Adds an info parameter
         
        `kind` can be ``"settings"`` (device settings parameter), ``"status"`` (device status parameter) or ``"full_info"`` (full device info).
        `getter`/`setter` are methods for getting/setting this parameter.
        Can be ``None``, meaning that this parameter is ingored when executing :func:`get_settings`/:func:`apply_settings`.
        """
        if kind not in self._info_nodes:
            raise ValueError("unrecognized info node kind: {}".format(kind))
        if not isinstance(ignore_error,tuple):
            ignore_error=(ignore_error,)
        self._info_nodes[kind][path]=(getter,setter,ignore_error)
        self._info_nodes_order[kind].append(path)
    def _add_full_info_node(self, path, getter=None, ignore_error=()):
        return self._add_info_node(path,"full_info",getter=getter,ignore_error=ignore_error)
    def _add_status_node(self, path, getter=None, ignore_error=()):
        return self._add_info_node(path,"status",getter=getter,ignore_error=ignore_error)
    def _add_settings_node(self, path, getter=None, setter=None, ignore_error=()):
        return self._add_info_node(path,"settings",getter=getter,setter=setter,ignore_error=ignore_error)
    def _get_info(self, kinds):
        """
        Get dict ``{name: value}`` containing all the device settings.
         
        `kinds` is the list of info nodes kinds to be included in the info.
        """
        for kind in kinds:
            if kind not in self._info_nodes:
                raise ValueError("unrecognized info node kind: {}".format(kind))
        info={}
        for kind in kinds:
            for k in self._info_nodes_order[kind]:
                g,_,err=self._info_nodes[kind][k]
                if g:
                    try:
                        info[k]=g()
                    except err+self._settings_ignore_error["get"]:
                        pass
        return info
    def get_settings(self):
        """Get dict ``{name: value}`` containing all the device settings."""
        return self._get_info(["settings"])
    def get_full_status(self):
        """Get dict ``{name: value}`` containing all the device settings."""
        return self._get_info(["settings","status"])
    def get_full_info(self):
        """Get dict ``{name: value}`` containing all the device settings."""
        return self._get_info(["settings","status","full_info"])
    def apply_settings(self, settings):
        """
        Apply the settings.
         
        `settings` is the dict ``{name: value}`` of the device available settings.
        Non-applicable settings are ignored.
        """
        for k in self._info_nodes_order["settings"]:
            _,s,err=self._info_nodes["settings"][k]
            if s and (k in settings):
                try:
                    s(settings[k])
                except err+self._settings_ignore_error["set"]:
                    pass
    def __getitem__(self, key):
        """Get the value of a settings, status, or full info parameter."""
        for kind in _info_node_kinds:
            if key in self._info_nodes[kind]:
                g=self._info_nodes[kind][key][0]
                if g:
                    return g()
                raise ValueError("no getter for value '{}'".format(key))
        raise KeyError("no property '{}'".format(key))
    def __setitem__(self, key, value):
        """Set the value of a settings parameter."""
        if key in self._info_nodes["settings"]:
            s=self._info_nodes["settings"][key][1]
            if s:
                return s(value)
            raise ValueError("no setter for value '{}'".format(key))
        raise KeyError("no property '{}'".format(key))