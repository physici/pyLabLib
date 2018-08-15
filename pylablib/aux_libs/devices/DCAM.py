from ...core.devio.interface import IDevice
from ...core.utils import py3, funcargparse

_depends_local=[".DCAM_lib","...core.devio.interface"]

import numpy as np
import collections
import ctypes
import contextlib

from .DCAM_lib import lib, DCAMLibError

class DCAMError(RuntimeError):
    "Generic Hamamatsu camera error."
class DCAMTimeoutError(DCAMError):
    "Timeout while waiting."

def get_cameras_number():
    """Get number of connected Hamamatsu cameras"""
    lib.initlib()
    return lib.dcamapi_init()

class DCAMCamera(IDevice):
    def __init__(self, idx=0):
        IDevice.__init__(self)
        lib.initlib()
        self.idx=idx
        self.handle=None
        self.dcamwait=None
        self.properties={}
        self._alloc_nframes=0
        self._default_nframes=100
        self.open()
        self._last_frame=None
        
    def open(self):
        """Open connection to the camera"""
        ncams=get_cameras_number()
        if self.idx>=ncams:
            raise DCAMError("camera index {} is not available ({} cameras exist)".format(self.idx,ncams))
        try:
            self.handle=lib.dcamdev_open(self.idx)
            self.dcamwait=lib.dcamwait_open(self.handle)
            self._update_properties_list()
        except DCAMLibError:
            self.close()
    def close(self):
        """Close connection to the camera"""
        if self.handle:
            lib.dcamwait_close(self.dcamwait.hwait)
            lib.dcamdev_close(self.handle)
        self.handle=None
    def is_opened(self):
        """Check if the device is connected"""
        return self.handle is not None


    ModelData=collections.namedtuple("ModelData",["vendor","model","serial_number","camera_version"])
    def get_model_data(self):
        """
        Get camera model data.

        Return tuple ``(vendor, model, serial_number, camera_version)``.
        """
        vendor=lib.dcamdev_getstring(self.handle,67109123)
        model=lib.dcamdev_getstring(self.handle,67109124)
        serial_number=lib.dcamdev_getstring(self.handle,67109122)
        camera_version=lib.dcamdev_getstring(self.handle,67109125)
        return self.ModelData(vendor,model,serial_number,camera_version)


    class Property(object):
        def __init__(self, cam_handle, name, id, min, max, step, default, unit):
            object.__init__(self)
            self.cam_handle=cam_handle
            self.name=name
            self.id=id
            self.min=min
            self.max=max
            self.step=step
            self.default=default
            self.unit=unit
        def as_text(self, value=None):
            """Get property value as text (by default, current value)"""
            if value is None:
                value=self.get_value()
            return lib.dcamprop_getvaluetext(self.cam_handle,self.id,value)
        def get_value(self):
            """Get current property value"""
            return lib.dcamprop_getvalue(self.cam_handle,self.id)
        def set_value(self, value):
            """Set property value"""
            return lib.dcamprop_setgetvalue(self.cam_handle,self.id,value)
        def __repr__(self):
            return "{}(name='{}', id={}, min={}, max={}, unit={})".format(self.__class__.__name__,self.name,self.id,self.min,self.max,self.unit)

    def list_properties(self):
        """Return list of all available properties"""
        ids=lib.dcamprop_getallids(self.handle,0)
        names=[lib.dcamprop_getname(self.handle,i) for i in ids]
        props=[lib.dcamprop_getattr(self.handle,i) for i in ids]
        props=[self.Property(self.handle,name,idx,p.valuemin,p.valuemax,p.valuestep,p.valuedefault,p.iUnit) for (idx,name,p) in zip(ids,names,props)]
        return props
    def _update_properties_list(self):
        props=self.list_properties()
        for p in props:
            self.properties[py3.as_str(p.name)]=p
    def get_value(self, name):
        """Get value of a property with the given name"""
        if name not in self.properties:
            raise DCAMError("can't find property {}".format(name))
        return self.properties[name].get_value()
    def set_value(self, name, value):
        """Set value of a property with the given name"""
        if name not in self.properties:
            raise DCAMError("can't find property {}".format(name))
        return self.properties[name].set_value(value)


    def set_trigger_mode(self, mode):
        """
        Set trigger mode.

        Can be ``"int"`` (internal), ``"ext"`` (external), or ``"software"`` (software trigger).
        """
        trigger_modes={"int":1,"ext":2,"software":3}
        funcargparse.check_parameter_range(mode,"mode",trigger_modes.keys())
        self.set_value("TRIGGER SOURCE",trigger_modes[mode])
    def setup_ext_trigger(self, invert=False, delay=0.):
        """Setup external trigger (inversion and delay)"""
        self.set_value("TRIGGER POLARITY",2 if invert else 1)
        self.set_value("TRIGGER DELAY",delay)
    def send_software_trigger(self):
        """Send software trigger signal"""
        lib.dcamcap_firetrigger(self.handle)
    def set_exposure(self, exposure):
        """Set camera exposure"""
        return self.set_value("EXPOSURE TIME",exposure)
    def get_exposure(self):
        """Set current exposure"""
        return self.get_value("EXPOSURE TIME")
    def get_readout_time(self):
        return self.get_value("TIMING READOUT TIME")

    def _allocate_buffer(self, nframes):
        self._deallocate_buffer()
        if nframes:
            lib.dcambuf_alloc(self.handle,nframes)
        self._alloc_nframes=nframes
    def _deallocate_buffer(self):
        lib.dcambuf_release(self.handle,0)
        self._alloc_nframes=0
        self._last_frame=None
    def _read_buffer(self, buffer):
        return lib.dcambuf_lockframe(self.handle,buffer)
    @contextlib.contextmanager
    def _reset_buffers(self):
        nframes=self._alloc_nframes
        self._deallocate_buffer()
        try:
            yield
        finally:
            self._allocate_buffer(nframes)
    def _buffer_to_array(self, buffer):
        bpp=int(buffer.bpp)
        if bpp==1:
            ct=ctypes.c_uint8*buffer.btot
        elif bpp==2:
            ct=ctypes.c_uint16*(buffer.btot//2)
        elif bpp==4:
            ct=ctypes.c_uint32*(buffer.btot//4)
        else:
            raise DCAMError("can't convert data with {} BBP into an array".format(bpp))
        data=ct.from_address(buffer.buf)
        return np.array(data).reshape((buffer.height,buffer.width))
    def get_ring_buffer_size(self):
        """Get the size of the allocated ring buffer (0 if no buffer is allocated)"""
        return self._alloc_nframes
    FrameInfo=collections.namedtuple("FrameInfo",["framestamp","timestamp_us","camerastamp","left","top","pixeltype"])
    def get_frame(self, buffer, return_info=False):
        """
        Get a frame at the given buffer index.

        If ``return_info==True``, return tuple ``(data, info)``, where info is the :class:`FrameInfo` instance
        describing frame index and timestamp, camera stamp, frame location on the sensor, and pixel type.
        """
        sframe=self._read_buffer(buffer)
        info=self.FrameInfo(sframe.framestamp,sframe.timestamp[0]*10**6+sframe.timestamp[1],sframe.camerastamp,sframe.left,sframe.top,sframe.pixeltype)
        data=self._buffer_to_array(sframe)
        return (data,info) if return_info else data

    def get_data_dimensions(self):
        """Get the current data dimension (taking ROI and binning into account)"""
        return (self.get_value("IMAGE HEIGHT"),self.get_value("IMAGE WIDTH"))
    def get_sensor_size(self):
        """Get the sensor size"""
        return (self.properties["SUBARRAY VSIZE"].max,self.properties["SUBARRAY HSIZE"].max)
    def get_roi(self):
        """
        Get current ROI.

        Return tuple ``(hstart, hend, vstart, vend, bin)`` (binning is the same for both axes).
        """
        hstart=self.get_value("SUBARRAY HPOS")
        hend=hstart+self.get_value("SUBARRAY HSIZE")
        vstart=self.get_value("SUBARRAY VPOS")
        vend=vstart+self.get_value("SUBARRAY VSIZE")
        bin=self.get_value("BINNING")
        return (hstart,hend,vstart,vend,bin)
    def set_roi(self, hstart=0, hend=None, vstart=0, vend=None, bin=1):
        """
        Set current ROI.

        By default, all non-supplied parameters take extreme values. Binning is the same for both axes.
        """
        self.set_value("SUBARRAY MODE",2)
        hend=hend or self.properties["SUBARRAY HSIZE"].max
        vend=vend or self.properties["SUBARRAY VSIZE"].max
        with self._reset_buffers():
            self.set_value("SUBARRAY HSIZE",self.properties["SUBARRAY HSIZE"].min)
            self.set_value("SUBARRAY HPOS",hstart)
            self.set_value("SUBARRAY HSIZE",hend-hstart)
            self.set_value("SUBARRAY VSIZE",self.properties["SUBARRAY VSIZE"].min)
            self.set_value("SUBARRAY VPOS",vstart)
            self.set_value("SUBARRAY VSIZE",vend-vstart)
            self.set_value("BINNING",bin)
        return self.get_roi()

    def start_acquisition(self, mode="sequence", nframes=None):
        """
        Start acquistion.

        `mode` can be either ``"snap"`` (since frame or sequency acquisition) or ``"sequence"`` (contunuous acquisition).
        `nframes` determines number of frames to acquire in ``"snap"`` mode, or size of the ring buffer in the ``"sequence"`` mode (by default, 100).
        """
        acq_modes=["sequence","snap"]
        funcargparse.check_parameter_range(mode,"mode",acq_modes)
        if nframes:
            self._allocate_buffer(nframes)
        elif not self._alloc_nframes:
            self._allocate_buffer(self._default_nframes)
        lib.dcamcap_start(self.handle,0 if mode=="snap" else -1)
        self._last_frame=-1
    def stop_acquisition(self):
        """Stop acquisition"""
        lib.dcamcap_stop(self.handle)
    def get_status(self):
        """
        Get acquisition status.

        Can be ``"busy"`` (capturing in progress), ``"ready"`` (ready for capturing),
        ``"stable"`` (not prepared for capturing), ``"unstable"`` (can't be prepared for capturing), or ``"error"`` (some other error).
        """
        status=["error","busy","ready","stable","unstable"]
        return status[lib.dcamcap_status(self.handle)]
    def get_transfer_info(self):
        """
        Get frame transfer info.

        Return tuple ``(last_buff, frame_count)``, where ``last_buff`` is the index of the last filled buffer,
        and ``frame_count`` is the total number of acquired frames.
        """
        return tuple(lib.dcamcap_transferinfo(self.handle,0))
    def get_new_images_range(self):
        """
        Get the range of the new images.
        
        Return tuple ``(first, last)`` with images range (inclusive).
        If no images are available, return ``None``.
        If some images werein the buffer were overwritten, exclude them from the range.
        """
        if self._last_frame is None:
            return None
        last_buff,frame_count=self.get_transfer_info()
        oldest_frame=max(self._last_frame+1,frame_count-self.get_ring_buffer_size())
        if oldest_frame==frame_count:
            return None
        return oldest_frame,frame_count-1



    def read_multiple_images(self, rng=None, return_info=False, peek=False):
        """
        Read multiple images specified by `rng` (by default, all un-read images).

        If ``return_info==True``, return tuple ``(data, info)``, where info is the :class:`FrameInfo` instance
        describing frame index and timestamp, camera stamp, frame location on the sensor, and pixel type.
        If ``peek==True``, return images but not mark them as read.
        """
        if rng is None:
            rng=self.get_new_images_range()
        dim=self.get_data_dimensions()
        if rng is None:
            return np.zeros((0,dim[1],dim[0]))
        frames=[self.get_frame(n%self._alloc_nframes,return_info=True) for n in range(rng[0],rng[1]+1)]
        images,infos=list(zip(*frames))
        images=np.array(images)
        if not peek:
            self._last_frame=rng[1]
        return (images,infos) if return_info else images
    def wait_for_frame(self, since="lastwait", timeout=20.):
        """
        Wait for a new camera frame.

        `since` specifies what constitutes a new frame.
        Can be ``"lastread"`` (wait for a new frame after the last read frame), ``"lastwait"`` (wait for a new frame after last :func:`wait_for_frame` call),
        or ``"now"`` (wait for a new frame acquired after this function call).
        If `timeout` is exceeded, rause :exc:`DCAMTimeoutError`.
        """
        funcargparse.check_parameter_range(since,"since",{"lastread","lastwait","now"})
        if since=="lastwait":
            timeout=int(timeout*1e3) if timeout is not None else 0x80000000
            try:
                lib.dcamwait_start(self.dcamwait.hwait,0x02,timeout)
            except DCAMLibError as e:
                if e.text_code=="DCAMERR_TIMEOUT":
                    raise DCAMTimeoutError
                else:
                    raise
        elif since=="lastread":
            while not self.get_new_images_range():
                self.wait_for_frame(since="lastwait",timeout=timeout)
        else:
            rng=self.get_new_images_range()
            last_img=rng[1] if rng else None
            while True:
                self.wait_for_frame(since="lastwait",timeout=timeout)
                rng=self.get_new_images_range()
                if rng and (last_img is None or rng[1]>last_img):
                    return

    def snap(self, return_info=False):
        """Snap a single image (with preset image read mode parameters)"""
        self.start_acquisition("snap",nframes=1)
        self.wait_for_frame()
        return self.get_frame(0,return_info=return_info)

    # ModelData=collections.namedtuple("ModelData",["controller_model","head_model","serial_number"])
    # def get_model_data(self):
    #     """
    #     Get camera model data.

    #     Return tuple ``(controller_mode, head_model, serial_number)``.
    #     """
    #     self._camsel()
    #     control_model=lib.GetControllerCardModel()
    #     head_model=lib.GetHeadModel()
    #     serial_number=lib.GetCameraSerialNumber()
    #     return self.ModelData(control_model,head_model,serial_number)
        
    # def get_capibilities(self):
    #     """
    #     Get camera capibilities.

    #     For description of the structure, see Andor SDK manual.
    #     """
    #     self._camsel()
    #     return lib.GetCapabilities()

    # ### Shutter controls ###
    # def get_min_shutter_times(self):
    #     """Get minimal shutter opening and closing times"""
    #     self._camsel()
    #     return lib.GetShutterMinTimes()
    # def set_shutter(self, mode, ttl_mode=0, open_time=None, close_time=None):
    #     """
    #     Setup shutter.

    #     `mode` can be ``"auto"``, ``"open"`` or ``"close"``, ttl_mode can be 0 (low is open) or 1 (high is open),
    #     `open_time` and `close_time` specify opening and closing times (required to calculate the minimal exposure times).
    #     By default, these time are minimal allowed times.
    #     """
    #     if mode in [0,False]:
    #         mode="close"
    #     if mode in [1,True]:
    #         mode="open"
    #     shutter_modes=["auto","open","close"]
    #     funcargparse.check_parameter_range(mode,"state",shutter_modes)
    #     self._camsel()
    #     min_open_time,min_close_time=self.get_min_shutter_times()
    #     open_time=min_open_time if open_time is None else open_time
    #     close_time=min_close_time if close_time is None else close_time
    #     lib.SetShutter(ttl_mode,shutter_modes.index(mode),open_time,close_time)
    #     self.shutter_mode=mode

    # ### Misc controls ###
    # def set_fan_mode(self, mode):
    #     """
    #     Set fan mode.

    #     Can be ``"full"``, ``"low"`` or ``"off"``.
    #     """
    #     text_modes=["full","low","off"]
    #     funcargparse.check_parameter_range(mode,"mode",text_modes)
    #     self._camsel()
    #     lib.SetFanMode(text_modes.index(mode))
    #     self.fan_mode=mode

    # def read_in_aux_port(self, port):
    #     """Get state at a given auxiliary port"""
    #     self._camsel()
    #     return lib.InAuxPort(port)
    # def set_out_aux_port(self, port, state):
    #     """Set state at a given auxiliary port"""
    #     self._camsel()
    #     return lib.OutAuxPort(port,state)