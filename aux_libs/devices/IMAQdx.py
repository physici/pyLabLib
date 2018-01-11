from . import IMAQdx_lib as lib

from ...core.utils import dictionary


class IMAQdxError(RuntimeError):
    """Generic IMAQdx error."""
    pass

class IMAQdxAttribute(object):
    def __init__(self, sid, name):
        object.__init__(self)
        self.sid=sid
        self.name=name
        self.display_name=lib.IMAQdxGetAttributeDisplayName(sid,name)
        self.tooltip=lib.IMAQdxGetAttributeTooltip(sid,name)
        self.description=lib.IMAQdxGetAttributeDescription(sid,name)
        self.units=lib.IMAQdxGetAttributeUnits(sid,name)
        self.readable=lib.IMAQdxIsAttributeReadable(sid,name)
        self.writable=lib.IMAQdxIsAttributeWritable(sid,name)
        self._attr_type=lib.IMAQdxGetAttributeType(sid,name)
        self.type=lib.IMAQdxAttributeType_enum[self._attr_type]
        if self._attr_type in [0,1,2,5]:
            self.min=lib.IMAQdxGetAttributeMinimum(sid,name,self._attr_type)
            self.max=lib.IMAQdxGetAttributeMaximum(sid,name,self._attr_type)
            self.inc=lib.IMAQdxGetAttributeIncrement(sid,name,self._attr_type)
        if self._attr_type==4:
            self.values=lib.IMAQdxEnumerateAttributeValues(sid,name)
    
    def get_value(self, enum_as_str=True):
        if not self.readable:
            raise IMAQdxError("Attribute {} is not readable".format(self.name))
        val=lib.IMAQdxGetAttribute(self.sid,self.name,self._attr_type)
        if self._attr_type==4 and enum_as_str:
            val=val.Name
        return val
    def set_value(self, value):
        if not self.writable:
            raise IMAQdxError("Attribute {} is not writable".format(self.name))
        return lib.IMAQdxSetAttribute(self.sid,self.name,value,None)

    def __repr__(self):
        return "{}({})".format(self.__class__.__name__,self.name)




def list_cameras(connected=True):
    return lib.IMAQdxEnumerateCameras(connected)

class IMAQdxCamera(object):
    def __init__(self, name="cam0", mode="controller", default_visibility="simple"):
        object.__init__(self)
        self.name=name
        self.mode=mode
        self.default_visibility=default_visibility
        self.sid=None
        self.open()
        try:
            attrs=self.list_attributes()
            self.attributes=dictionary.Dictionary(dict([ (a.name.replace("::","/"),a) for a in attrs ]))
        except lib.IMAQdxLibError:
            self.close()

    def open(self, mode=None):
        mode=self.mode if mode is None else mode
        mode=lib.IMAQdxCameraControlMode_enum.get(mode,mode)
        self.sid=lib.IMAQdxOpenCamera(self.name,mode)
    def close(self):
        if self.sid is not None:
            lib.IMAQdxCloseCamera(self.sid)
            self.sid=None

    def list_attributes(self, root="", visibility=None):
        visibility=visibility or self.default_visibility
        visibility=lib.IMAQdxAttributeVisibility_enum.get(visibility,visibility)
        root.replace("/","::")
        attrs=lib.IMAQdxEnumerateAttributes2(self.sid,root,visibility)
        return [IMAQdxAttribute(self.sid,a.Name) for a in attrs]

    def get_value(self, name):
        name.replace("::","/")
        return self.attributes[name].get_value()
    __getitem__=get_value
    def set_value(self, name, value):
        name.replace("::","/")
        self.attributes[name].set_value(value)
    __setitem__=set_value

    def get_settings(self):
        return self.attributes.copy().filter_self(lambda a: a.readable).map_self(lambda a: a.get_value())
    def apply_settings(self, settings):
        for k in settings:
            if k in self.attributes and self.attributes[k].writable:
                self.attributes[k].set_value(settings[k])

    def setup_acqusition(self, continuous, frames):
        lib.IMAQdxConfigureAcquisition(self.sid,continuous,frames)
    def clear_acquisition(self):
        lib.IMAQdxUnconfigureAcquisition(self.sid)
    def start_acquisition(self):
        lib.IMAQdxStartAcquisition(self.sid)
    def stop_acquisition(self):
        lib.IMAQdxStopAcquisition(self.sid)

    def read_data_raw(self, size_bytes, mode, buffer_num=0):
        return lib.IMAQdxGetImageData(size_bytes,mode,buffer_num)