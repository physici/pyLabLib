### Interface for a generic device class ###

class IDevice(object):
    """
    A base class for an instrument.
    
    Contains some useful functions for dealing with device settings.
    """
    def __init__(self):
        object.__init__(self)
        self._settings_nodes={}
        self._settings_nodes_order=[]
        
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
    
    
    def _add_settings_node(self, path, getter=None, setter=None, ignore_error=()):
        """
        Adds a settings parameter
        
        `getter`/`setter` are methods for getting/setting this parameter.
        Can be ``None``, meaning that this parameter is ingored when executing :func:`get_settings`/:func:`apply_settings`.
        """
        self._settings_nodes[path]=(getter,setter,ignore_error)
        self._settings_nodes_order.append(path)
    def get_settings(self):
        """Get dict ``{name: value}`` containing all the device settings."""
        settings={}
        for k in self._settings_nodes_order:
            g,_,err=self._settings_nodes[k]
            if g:
                try:
                    settings[k]=g()
                except err:
                    pass
        return settings
    def apply_settings(self, settings):
        """
        Apply the settings.
        
        `settings` is the dict ``{name: value}`` of the device available settings.
        Non-applicable settings are ignored.
        """
        for k in self._settings_nodes_order:
            _,s,err=self._settings_nodes[k]
            if s and (k in settings):
                try:
                    s(settings[k])
                except err:
                    pass
    def __getitem__(self, key):
        """Get the value of a settings parameter."""
        if key in self._settings_nodes:
            g=self._settings_nodes[key][0]
            if g:
                return g()
            raise ValueError("no getter for value '{}'".format(key))
        raise KeyError("no property '{}'".format(key))
    def __setitem__(self, key, value):
        """Set the value of a settings parameter."""
        if key in self._settings_nodes:
            s=self._settings_nodes[key][1]
            if s:
                return s(value)
            raise ValueError("no setter for value '{}'".format(key))
        raise KeyError("no property '{}'".format(key))