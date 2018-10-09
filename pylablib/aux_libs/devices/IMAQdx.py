from ...core.utils import dictionary, py3
from ...core.devio import data_format

import numpy as np
import contextlib
import time


from . import IMAQdx_lib
lib=IMAQdx_lib.lib
try:
    lib.initlib()
except (ImportError, OSError):
    pass
IMAQdxError=IMAQdx_lib.IMAQdxGenericError

_depends_local=[".IMAQdx_lib"]

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
        self.type=IMAQdx_lib.IMAQdxAttributeType_enum[self._attr_type]
        if self._attr_type in [0,1,2,5]:
            self.min=lib.IMAQdxGetAttributeMinimum(sid,name,self._attr_type)
            self.max=lib.IMAQdxGetAttributeMaximum(sid,name,self._attr_type)
            self.inc=lib.IMAQdxGetAttributeIncrement(sid,name,self._attr_type)
        if self._attr_type==4:
            self.values=lib.IMAQdxEnumerateAttributeValues(sid,name)
    
    def update_minmax(self):
        if self._attr_type in [0,1,2,5]:
            self.min=lib.IMAQdxGetAttributeMinimum(self.sid,self.name,self._attr_type)
            self.max=lib.IMAQdxGetAttributeMaximum(self.sid,self.name,self._attr_type)
            self.inc=lib.IMAQdxGetAttributeIncrement(self.sid,self.name,self._attr_type)
    def truncate_value(self, value):
        self.update_minmax()
        if self._attr_type in [0,1,2,5]:
            if value<self.min:
                value=self.min
            elif value>self.max:
                value=self.max
            else:
                inc=self.inc
                if inc>0:
                    value=((value-self.min)//inc)*inc+self.min
        return value

    def get_value(self, enum_as_str=True):
        if not self.readable:
            raise IMAQdxError("Attribute {} is not readable".format(self.name))
        val=lib.IMAQdxGetAttribute(self.sid,self.name,self._attr_type)
        if self._attr_type==4 and enum_as_str:
            val=val.Name
        return val
    def set_value(self, value, truncate=True):
        if not self.writable:
            raise IMAQdxError("Attribute {} is not writable".format(self.name))
        if truncate:
            value=self.truncate_value(value)
        return lib.IMAQdxSetAttribute(self.sid,self.name,value,None)

    def __repr__(self):
        return "{}({})".format(self.__class__.__name__,self.name)




def list_cameras(connected=True):
    return lib.IMAQdxEnumerateCameras(connected)

class IMAQdxCamera(object):
    def __init__(self, name="cam0", mode="controller", default_visibility="simple"):
        object.__init__(self)
        self.init_done=False
        self.name=name
        self.mode=mode
        self.default_visibility=default_visibility
        self.sid=None
        self.open()
        try:
            attrs=self.list_attributes()
            self.attributes=dictionary.Dictionary(dict([ (a.name.replace("::","/"),a) for a in attrs ]))
        except Exception:
            self.close()
            raise
        self.init_done=True
        self.post_open()

    def post_open(self):
        pass
    def open(self, mode=None):
        mode=self.mode if mode is None else mode
        mode=IMAQdx_lib.IMAQdxCameraControlMode_enum.get(mode,mode)
        self.sid=lib.IMAQdxOpenCamera(self.name,mode)
        self.post_open()
    def close(self):
        if self.sid is not None:
            lib.IMAQdxCloseCamera(self.sid)
            self.sid=None
    def reset(self):
        self.close()
        lib.IMAQdxResetCamera(self.name,False)
        self.open()
    def __enter__(self):
        return self
    def __exit__(self, *args, **vargs):
        self.close()
        return False

    def list_attributes(self, root="", visibility=None):
        visibility=visibility or self.default_visibility
        visibility=IMAQdx_lib.IMAQdxAttributeVisibility_enum.get(visibility,visibility)
        root.replace("/","::")
        attrs=lib.IMAQdxEnumerateAttributes2(self.sid,root,visibility)
        return [IMAQdxAttribute(self.sid,a.Name) for a in attrs]

    def get_value(self, name, default=None):
        name.replace("::","/")
        if (default is not None) and (name not in self.attributes):
            return default
        v=self.attributes[name].get_value()
        if isinstance(v,py3.new_bytes):
            v=py3.as_str(v)
        return v
    __getitem__=get_value
    def set_value(self, name, value, ignore_missing=False, truncate=True):
        name.replace("::","/")
        if (name in self.attributes) or (not ignore_missing):
            self.attributes[name].set_value(value,truncate=truncate)
    __setitem__=set_value

    def get_settings(self, as_dict=False):
        settings=self.attributes.copy().filter_self(lambda a: a.readable).map_self(lambda a: a.get_value())
        return settings.as_dict(style="flat") if as_dict else settings
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
    def acquision_in_progress(self):
        return self["StatusInformation/AcqInProgress"]
    def refresh_acquisition(self, delay=0.005):
        self.stop_acquisition()
        self.clear_acquisition()
        self.setup_acqusition(0,1)
        self.start_acquisition()
        time.sleep(delay)
        self.stop_acquisition()
        self.clear_acquisition()
    
    @contextlib.contextmanager
    def pausing_acuisition(self):
        acq_in_progress=self.acquision_in_progress()
        self.stop_acquisition()
        try:
            yield
        finally:
            if acq_in_progress:
                self.start_acquisition()

    def read_data_raw(self, size_bytes, mode, buffer_num=0):
        mode=IMAQdx_lib.IMAQdxBufferNumberMode_enum.get(mode,mode)
        return lib.IMAQdxGetImageData(self.sid,size_bytes,mode,buffer_num)







class IMAQdxPhotonFocusCamera(IMAQdxCamera):
    def __init__(self, name, mode="controller", default_visibility="simple", small_packet_size=True):
        self.small_packet_size=small_packet_size
        IMAQdxCamera.__init__(self,name,mode=mode,default_visibility=default_visibility)
        self.frame_counter=0
    def post_open(self):
        if self.init_done and self.small_packet_size:
            self.set_value("AcquisitionAttributes/PacketSize",1500,ignore_missing=True)

    def get_exposure(self):
        return self["CameraAttributes/AcquisitionControl/ExposureTime"]*1E-6
    def set_exposure(self, exposure):
        with self.pausing_acuisition():
            self["CameraAttributes/AcquisitionControl/ExposureTime"]=exposure*1E6
        return self.get_exposure()

    def get_detector_size(self):
        return self.attributes["CameraAttributes/ImageFormatControl/Width"].max,self.attributes["CameraAttributes/ImageFormatControl/Height"].max
    def get_roi(self):
        ox=self["CameraAttributes/ImageFormatControl/OffsetX"]
        oy=self["CameraAttributes/ImageFormatControl/OffsetY"]
        return ox+1,ox+self["CameraAttributes/ImageFormatControl/Width"],oy+1,oy+self["CameraAttributes/ImageFormatControl/Height"]
    def set_roi(self, hstart=1, hend=None, vstart=1, vend=None):
        det_size=self.get_detector_size()
        if hend is None:
            hend=det_size[0]
        if vend is None:
            vend=det_size[1]
        with self.pausing_acuisition():
            self["CameraAttributes/ImageFormatControl/Width"]=self.attributes["CameraAttributes/ImageFormatControl/Width"].min
            self["CameraAttributes/ImageFormatControl/Height"]=self.attributes["CameraAttributes/ImageFormatControl/Height"].min
            self["CameraAttributes/ImageFormatControl/OffsetX"]=hstart-1
            self["CameraAttributes/ImageFormatControl/OffsetY"]=vstart-1
            self["CameraAttributes/ImageFormatControl/Width"]=hend-hstart+1
            self["CameraAttributes/ImageFormatControl/Height"]=vend-vstart+1
        return self.get_roi()

    def setup_acqusition(self, continuous, frames):
        IMAQdxCamera.setup_acqusition(self,continuous,frames)
        if continuous:
            self.buffers_num=frames//2 # seems to be the case
        else:
            self.buffers_num=frames
    def start_acquisition(self):
        IMAQdxCamera.start_acquisition(self)
        self.frame_counter=0
    def _last_buffer(self):
        return self["StatusInformation/LastBufferNumber"]
    def _last_buffer_count(self):
        return self["StatusInformation/LastBufferCount"]
    def new_frames_num(self):
        return self._last_buffer_count()-self.frame_counter
    def wait_for_frame(self, timeout=None, sleepstep=1E-3):
        t=time.time()
        while (timeout is None) or (time.time()<t+timeout):
            new_frames=self.new_frames_num()
            if new_frames:
                return new_frames
            time.sleep(sleepstep)


    def _get_bpp(self):
        pform=self["CameraAttributes/ImageFormatControl/PixelFormat"]
        if pform.startswith("Mono"):
            pform=pform[4:]
            if pform.endswith("Packed"):
                raise IMAQdxError("packed pixel format isn't currently supported: {}".format("Mono"+pform))
            try:
                return (int(pform)-1)//8+1
            except ValueError:
                pass
        raise IMAQdxError("unrecognized pixel format: {}".format(pform))
    def _frame_size_bytes(self):
        roi=self.get_roi()
        return (roi[1]-roi[0]+1)*(roi[3]-roi[2]+1)*self._get_bpp()
    def _bytes_to_frame(self, raw_data):
        roi=self.get_roi()
        bpp=self._get_bpp()
        dtype=data_format.DataFormat(bpp,"i","<")
        return np.fromstring(raw_data,dtype=dtype.to_desc("numpy")).reshape((roi[3]-roi[2]+1,roi[1]-roi[0]+1))
    def peek_frame(self, mode="last", buffer_num=0):
        raw_data,buffer_num=self.read_data_raw(self._frame_size_bytes(),mode=mode,buffer_num=buffer_num)
        return self._bytes_to_frame(raw_data),buffer_num
    def read_frames(self, frames_num=None):
        new_frames=self.new_frames_num()
        if frames_num is None:
            frames_num=new_frames
        else:
            frames_num=min(frames_num,new_frames)
        frames=[]
        for i in range(frames_num):
            _,buff=self.read_data_raw(0,2,self.frame_counter)
            if buff!=self.frame_counter:
                frames.append(None)
            else:
                frame,buff=self.peek_frame("number",self.frame_counter)
                if buff==self.frame_counter:
                    frames.append(frame)
            self.frame_counter+=1
        return frames
    def skip_frames(self, frames_num=None):
        new_frames=self.new_frames_num()
        if frames_num is None:
            frames_num=new_frames
        else:
            frames_num=min(frames_num,new_frames)
        self.frame_counter+=frames_num

    def snap(self):
        self.refresh_acquisition()
        self.setup_acqusition(0,1)
        self.start_acquisition()
        self.wait_for_frame()
        frame=self.read_frames()[0]
        self.stop_acquisition()
        self.clear_acquisition()
        return frame