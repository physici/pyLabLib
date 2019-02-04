from ...core.utils import dictionary, py3, general
from ...core.devio import data_format, interface
from ...core.dataproc import image as image_utils

import numpy as np
import contextlib
import time
import collections
import re

from .IMAQdx import IMAQdxPhotonFocusCamera as PhotonFocusIMAQdxCamera
from .IMAQ import IMAQCamera, IMAQError
from . import pfcam_lib
lib=pfcam_lib.lib
try:
    lib.initlib()
except (ImportError, OSError):
    pass
PfcamError=pfcam_lib.PfcamLibError
class PFGenericError(RuntimeError):
    "Generic IMAQ camera error."

_depends_local=[".pfcam_lib",".IMAQ",".IMAQdx","...core.devio.interface"]

class PfcamProperty(object):
    """
    Object representing a pfcam camera property.

    Allows to query and set values and get additional information.
    Usually created automatically by an :class:`PFCamera` instance, but could be created manually.

    Attributes:
        name: attirbute name
        readable (bool): whether property is readable
        writable (bool): whether property is writable
        is_command (bool): whether property is a command
        min (float or int): minimal property value (if applicable)
        max (float or int): maximal property value (if applicable)
        values: list of possible property values (if applicable)
    """
    def __init__(self, port, name):
        object.__init__(self)
        self.port=port
        self.name=py3.as_str(name)
        self._token=lib.pfProperty_ParseName(port,self.name)
        if self._token==pfcam_lib.PfInvalidToken:
            raise PFGenericError("property {} doesn't exist".format(name))
        self._type=pfcam_lib.TPropertyType[lib.pfProperty_GetType(port,self._token)]
        if self._type not in pfcam_lib.ValuePropertyTypes|{"PF_COMMAND"}:
            raise PFGenericError("property type {} not supported".format(self._type))
        self._flags=lib.pfProperty_GetFlags(port,self._token)
        if self._flags&0x42:
            raise PFGenericError("propery {} is private or invalid".format(self.name))
        self.is_command=self._type=="PF_COMMAND"
        self.readable=not (self._flags&0x20 or self.is_command)
        self.writable=not (self._flags&0x10 or self.is_command)
        if self._type in {"PF_INT","PF_UINT","PF_FLOAT"}:
            self.min=lib.get_property_by_name(port,self.name+".Min")
            self.max=lib.get_property_by_name(port,self.name+".Max")
        else:
            self.min=self.max=None
        if self._type=="PF_MODE":
            self._values_dict={}
            self._values_dict_inv={}
            nodes=lib.collect_properties(port,self._token,backbone=False)
            for tok,val in nodes:
                val=py3.as_str(val)
                if lib.pfProperty_GetType(port,tok)==2: # integer token, means one of possible values
                    ival=lib.pfDevice_GetProperty(port,tok)
                    self._values_dict[val]=ival
                    self._values_dict_inv[ival]=val
            self.values=list(self._values_dict)
        else:
            self._values_dict=self._values_dict_inv={}
            self.values=None
    
    def update_minmax(self):
        """Update minimal and maximal property limits"""
        if self._type in {"PF_INT","PF_UINT","PF_FLOAT"}:
            self.min=lib.get_property_by_name(self.port,self.name+".Min")
            self.max=lib.get_property_by_name(self.port,self.name+".Max")
    def truncate_value(self, value):
        """Truncate value to lie within property limits"""
        self.update_minmax()
        if self.min is not None and value<self.min:
            value=self.min
        if self.max is not None and value>self.max:
            value=self.max
        return value

    def get_value(self, enum_as_str=True):
        """
        Get property value.
        
        If ``enum_as_str==True``, return enum-style values as strings; otherwise, return corresponding integer values.
        """
        if not self.readable:
            raise PFGenericError("property {} is not readable".format(self.name))
        val=lib.pfDevice_GetProperty(self.port,self._token)
        if self._type=="PF_MODE" and enum_as_str:
            val=self._values_dict_inv[val]
        return val
    def set_value(self, value, truncate=True):
        """
        Get property value.
        
        If ``truncate==True``, automatically truncate value to lie within allowed range.
        """
        if not self.writable:
            raise PFGenericError("property {} is not writable".format(self.name))
        if truncate:
            value=self.truncate_value(value)
        if isinstance(value,py3.anystring) and self._type=="PF_MODE":
            value=self._values_dict[value]
        lib.pfDevice_SetProperty(self.port,self._token,value)
        return self.get_value()
    def call_command(self, arg=0):
        """If property is a command, call it with a given argument; otherwise, raise an error."""
        if not self.is_command:
            raise PFGenericError("{} is not a PF_COMMAND property".format(self.name))
        lib.pfDevice_SetProperty(self.port,self._token,arg)

    def __repr__(self):
        return "{}({})".format(self.__class__.__name__,self.name)







def query_camera_name(port):
    """Query cameras name at a given port in pfcam interface"""
    lib.pfPortInit()
    try:
        raw_name=lib.pfProperty_GetName(port,lib.pfDevice_GetRoot(port))
        return py3.as_str(raw_name) if raw_name is not None else None
    except pfcam_lib.PfcamLibError:
        lib.pfDeviceOpen(port)
        value=query_camera_name(port)
        lib.pfDeviceClose(port)
def list_cameras(supported=False):
    """
    List all cameras available through pfcam interface
    
    If ``supported==True'', only return cameras which support pfcam protocol.
    """
    ports=range(lib.pfPortInit())
    if supported:
        ports=[p for p in ports if query_camera_name(p) is not None]
    return [(p,lib.pfPortInfo(p)) for p in ports]







class PhotonFocusIMAQCamera(IMAQCamera):
    """
    IMAQ+PFcam interface to a PhotonFocus camera.

    Args:
        imaq_name: IMAQ interface name (can be learned by :func:`IMAQ.list_cameras`; usually, but not always, starts with ``"img"``)
        pfcam_port: port number for pfcam interface (can be learned by :func:`list_cameras`; port number is the first element of the camera data tuple)
    """
    def __init__(self, imaq_name="img0", pfcam_port=0):
        self.pfcam_port=pfcam_port
        try:
            IMAQCamera.__init__(self)
            props=self.list_properties()
            self.properties=dictionary.Dictionary(dict([ (p.name.replace(".","/"),p) for p in props ]))
            self.v=dictionary.ItemAccessor(self.get_value,self.set_value)
            self._update_imaq()
        except Exception:
            self.close()
            raise

        self._add_full_info_node("model_data",self.get_model_data)
        self._add_full_info_node("interface_name",lambda: self.name)
        self._add_full_info_node("pfcam_port",lambda: self.pfcam_port)
        self._add_status_node("properties",self.get_all_properties)
        self._add_settings_node("exposure",self.get_exposure,self.set_exposure)
        
    def open(self):
        """Open connection to the camera"""
        IMAQCamera.open(self)
        lib.pfPortInit()
        lib.pfDeviceOpen(self.pfcam_port)
        self.post_open()
    def close(self):
        """Close connection to the camera"""
        IMAQCamera.close(self)
        lib.pfDeviceClose(self.pfcam_port)

    def post_open(self):
        """Action to automatically call on opening"""
        pass

    def list_properties(self, root=""):
        """
        List all properties at a given root.

        Return list of :class:`PfcamProperty` objects, which allow querying and settings values
        and getting additional information (limits, values).
        """
        root=root.replace("/",".")
        pfx=root
        if root=="":
            root=lib.pfDevice_GetRoot(self.pfcam_port)
        else:
            root=lib.pfProperty_ParseName(self.pfcam_port,root)
        props=lib.collect_properties(self.pfcam_port,root,pfx=pfx,include_types=pfcam_lib.ValuePropertyTypes|{"PF_COMMAND"})
        pfprops=[]
        for (_,name) in props:
            try:
                pfprops.append(PfcamProperty(self.pfcam_port,name))
            except PFGenericError:
                pass
        return pfprops

    def get_value(self, name, default=None):
        """Get value of the property with a given name"""
        name=name.replace(".","/")
        if (default is not None) and (name not in self.properties):
            return default
        if self.properties.is_dictionary(self.properties[name]):
            return self.get_all_properties(root=name)
        v=self.properties[name].get_value()
        return v
    def _get_value_direct(self, name):
        return lib.get_property_by_name(self.pfcam_port,name)
    def set_value(self, name, value, ignore_missing=False, truncate=True):
        """
        Set value of the property with a given name.
        
        If ``truncate==True``, truncate value to lie within property range.
        """
        name=name.replace(".","/")
        if (name in self.properties) or (not ignore_missing):
            if self.properties.is_dictionary(self.properties[name]):
                self.set_all_properties(value,root=name)
            else:
                self.properties[name].set_value(value,truncate=truncate)
    def call_command(self, name, arg=0, ignore_missing=False):
        """If property is a command, call it with a given argument; otherwise, raise an error."""
        name=name.replace(".","/")
        if (name in self.properties) or (not ignore_missing):
            self.properties[name].call_command(arg=arg)

    def get_all_properties(self, root="", as_dict=False):
        """
        Get values of all properties with the given `root`.

        If ``as_dict==True``, return ``dict`` object; otherwise, return :class:`Dictionary` object.
        """
        settings=self.properties[root].copy().filter_self(lambda a: a.readable).map_self(lambda a: a.get_value())
        return settings.as_dict(style="flat") if as_dict else settings
    def set_all_properties(self, settings, root="", truncate=True):
        """
        Set values of all properties with the given `root`.
        
        If ``truncate==True``, truncate value to lie within attribute range.
        """
        settings=dictionary.as_dict(settings,style="flat",copy=False)
        for k in settings:
            if k in self.properties[root] and self.properties[root,k].writable:
                self.properties[root,k].set_value(settings[k],truncate=truncate)


    ModelData=collections.namedtuple("ModelData",["model","serial_number"])
    def get_model_data(self):
        """
        Get camera model data.

        Return tuple ``(model, serial_number)``.
        """
        model=query_camera_name(self.pfcam_port)
        serial_number=self.get_value("Header.Serial",0)
        return self.ModelData(model,serial_number)


    def _get_pf_data_dimensions_rc(self):
        return self.v["Window/H"],self.v["Window/W"]
    def _update_imaq(self):
        r,c=self._get_pf_data_dimensions_rc()
        IMAQCamera.set_roi(self,0,c,0,r)
    def get_roi(self):
        """
        Get current ROI.

        Return tuple ``(hstart, hend, vstart, vend)``.
        """
        ox=self.v.get("Window/X",0)
        oy=self.v.get("Window/Y",0)
        w=self.v["Window/W"]
        h=self.v["Window/H"]
        return ox,ox+w,oy,oy+h
    def set_roi(self, hstart=0, hend=None, vstart=0, vend=None):
        """
        Setup camera ROI.

        By default, all non-supplied parameters take extreme values.
        """
        for a in ["Window/X","Window/Y","Window/W","Window/H"]:
            if a not in self.properties or not self.properties[a].writable:
                return
        det_size=self.get_detector_size()
        if hend is None:
            hend=det_size[0]
        if vend is None:
            vend=det_size[1]
        with self.pausing_acquisition():
            self.v["Window/W"]=self.properties["Window/W"].min
            self.v["Window/H"]=self.properties["Window/H"].min
            self.v["Window/X"]=hstart
            self.v["Window/Y"]=vstart
            self.v["Window/W"]=max(self.v["Window/W"],hend-hstart)
            self.v["Window/H"]=max(self.v["Window/H"],vend-vstart)
            self._update_imaq()
        return self.get_roi()
    def get_roi_limits(self):
        """
        Get the minimal and maximal ROI parameters.

        Return tuple ``(min_roi, max_roi)``, where each element is in turn 4-tuple describing the ROI.
        """
        params=["Window/X","Window/Y","Window/W","Window/H"]
        for p in params:
            self.properties[p].update_minmax()
        minp=tuple([(self.properties[p].min if p in self.properties else 0) for p in params])
        maxp=tuple([(self.properties[p].max if p in self.properties else 0) for p in params])
        min_roi=(0,0)+minp[2:]
        max_roi=maxp
        return (min_roi,max_roi)

    def _get_buffer_bpp(self):
        bpp=IMAQCamera._get_buffer_bpp(self)
        if "DataResolution" in self.properties:
            res=self.v["DataResolution"]
            m=re.match(r"Res(\d+)Bit",res)
            if m:
                bpp=(int(m.group(1))-1)//8+1
        return bpp

    def get_exposure(self):
        """Get current exposure"""
        return self.v["ExposureTime"]*1E-3
    def set_exposure(self, exposure):
        """Set current exposure"""
        with self.pausing_acquisition():
            self.v["ExposureTime"]=exposure*1E3
        return self.get_exposure()

    def get_frame_time(self):
        """Get current frame time"""
        return self.v["FrameTime"]*1E-3
    def set_frame_time(self, frame_time):
        """Set current frame time"""
        with self.pausing_acquisition():
            self.v["FrameTime"]=frame_time*1E3
        return self.get_frame_time()