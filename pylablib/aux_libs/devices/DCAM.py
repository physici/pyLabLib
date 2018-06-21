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
            if value is None:
                value=self.get_value()
            return lib.dcamprop_getvaluetext(self.cam_handle,self.id,value)
        def get_value(self):
            return lib.dcamprop_getvalue(self.cam_handle,self.id)
        def set_value(self, value):
            return lib.dcamprop_setgetvalue(self.cam_handle,self.id,value)
        def __repr__(self):
            return "{}(name='{}', id={}, min={}, max={}, unit={})".format(self.__class__.__name__,self.name,self.id,self.min,self.max,self.unit)

    def list_properties(self):
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
        if name not in self.properties:
            raise DCAMError("can't find property {}".format(name))
        return self.properties[name].get_value()
    def set_value(self, name, value):
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
        self._camsel()
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
        return self._alloc_nframes
    FrameInfo=collections.namedtuple("FrameInfo",["framestamp","timestamp_us","camerastamp","left","top","pixeltype"])
    def get_frame(self, buffer, return_info=False):
        sframe=self._read_buffer(buffer)
        info=self.FrameInfo(sframe.framestamp,sframe.timestamp[0]*10**6+sframe.timestamp[1],sframe.camerastamp,sframe.left,sframe.top,sframe.pixeltype)
        data=self._buffer_to_array(sframe)
        return (data,info) if return_info else data

    def get_data_dimensions(self):
        return (self.get_value("IMAGE HEIGHT"),self.get_value("IMAGE WIDTH"))
    def get_sensor_size(self):
        return (self.properties["SUBARRAY VSIZE"].max,self.properties["SUBARRAY HSIZE"].max)
    def get_roi(self):
        hstart=self.get_value("SUBARRAY HPOS")
        hend=hstart+self.get_value("SUBARRAY HSIZE")
        vstart=self.get_value("SUBARRAY VPOS")
        vend=vstart+self.get_value("SUBARRAY VSIZE")
        bin=self.get_value("BINNING")
        return (hstart,hend,vstart,vend,bin)
    def set_roi(self, hstart=0, hend=None, vstart=0, vend=None, bin=1):
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
        acq_modes=["sequence","snap"]
        funcargparse.check_parameter_range(mode,"mode",acq_modes)
        if nframes:
            self._allocate_buffer(nframes)
        elif not self._alloc_nframes:
            self._allocate_buffer(self._default_nframes)
        lib.dcamcap_start(self.handle,0 if mode=="snap" else -1)
        self._last_frame=-1
    def stop_acquisition(self):
        lib.dcamcap_stop(self.handle)
    def get_status(self):
        status=["error","busy","ready","stable","unstable"]
        return status[lib.dcamcap_status(self.handle)]
    def get_transfer_info(self):
        return tuple(lib.dcamcap_transferinfo(self.handle,0))
    def get_new_images_range(self):
        if self._last_frame is None:
            return None
        last_buff,frame_count=self.get_transfer_info()
        oldest_frame=max(self._last_frame+1,frame_count-self.get_ring_buffer_size())
        if oldest_frame==frame_count:
            return None
        return oldest_frame,frame_count-1



    def read_multiple_images(self, rng=None, return_info=False, peek=False):
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
        If `timeout` is exceeded, rause :exc:`AndorTimeoutError`.
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
        

    # ### Generic controls ###
    # def get_status(self):
    #     """
    #     Get camera status.

    #     Return either ``"idle"`` (no acquisition), ``"acquiring"`` (acquisition in progress) or ``"temp_cycle"`` (temperature cycle in progress).
    #     """
    #     self._camsel()
    #     status=lib.GetStatus()
    #     text_status=lib.Andor_statuscodes[status]
    #     if text_status=="DRV_IDLE":
    #         return "idle"
    #     if text_status=="DRV_TEMPCYCLE":
    #         return "temp_cycle"
    #     if text_status=="DRV_ACQUIRING":
    #         return "acquiring"
    #     raise AndorLibError("GetStatus",status)
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

    # ### Trigger controls ###
    # def set_trigger_mode(self, mode):
    #     """
    #     Set trigger mode.

    #     Can be ``"int"`` (internal), ``"ext"`` (external), ``"ext_start"`` (external start), ``"ext_exp"`` (external exposure),
    #     ``"ext_fvb_em"`` (external FVB EM), ``"software"`` (software trigger) or ``"ext_charge_shift"`` (external charge shifting).

    #     For description, see Andor SDK manual.
    #     """
    #     trigger_modes={"int":0,"ext":1,"ext_start":6,"ext_exp":7,"ext_fvb_em":9,"software":10,"ext_charge_shift":12}
    #     funcargparse.check_parameter_range(mode,"mode",trigger_modes.keys())
    #     self._camsel()
    #     lib.SetTriggerMode(trigger_modes[mode])
    #     self.trigger_mode=mode
    # def get_trigger_level_limits(self):
    #     """Get limits on the trigger level"""
    #     self._camsel()
    #     return lib.GetTriggerLevelRange()
    # def setup_ext_trigger(self, level, invert, term_highZ=True):
    #     """Setup external trigger (level, inversion, and high-Z termination)"""
    #     self._camsel()
    #     lib.SetTriggerLevel(level)
    #     lib.SetTriggerInvert(invert)
    #     lib.SetExternalTriggerTermination(term_highZ)
    # def send_software_trigger(self):
    #     """Send software trigger signal"""
    #     self._camsel()
    #     lib.SendSoftwareTrigger()

    # ### Acquisition mode controls ###
    # _acq_modes={"single":1,"accum":2,"kinetics":3,"fast_kinetics":4,"cont":5}
    # def set_acquisition_mode(self, mode):
    #     """
    #     Set acquisition mode.

    #     Can be ``"single"``, ``"accum"``, ``"kinetics"``, ``"fast_kinetics"`` or ``"cont"`` (continuous).
    #     For description of each mode, see Andor SDK manual and corresponding setup_*_mode functions.
    #     """
    #     funcargparse.check_parameter_range(mode,"mode",self._acq_modes.keys())
    #     self._camsel()
    #     lib.SetAcquisitionMode(self._acq_modes[mode])
    #     self.acq_mode=mode
    # def setup_accum_mode(self, num, cycle_time=0):
    #     """
    #     Setup accum acquisition mode.
        
    #     `num` is the number of accumulated frames, `cycle_time` is the acquistion period
    #     (by default the minimal possible based on exposure and transfer time).
    #     """
    #     self._camsel()
    #     self.set_acquisition_mode("accum")
    #     lib.SetNumberAccumulations(num)
    #     lib.SetAccumulationCycleTime(cycle_time)
    #     self.acq_params["accum"]=(num,cycle_time)
    # def setup_kinetic_mode(self, num, cycle_time=0., num_acc=1, cycle_time_acc=0, num_prescan=0):
    #     """
    #     Setup kinetic acquisition mode.
        
    #     `num` is the number of kinteic cycles frames, `cycle_time` is the acquistion period between accum frames,
    #     `num_accum` is the number of accumulated frames, `cycle_time_acc` is the accum acquistion period,
    #     `num_prescan` is the number of prescans.
    #     """
    #     self._camsel()
    #     self.set_acquisition_mode("kinetics")
    #     lib.SetNumberKinetics(num)
    #     lib.SetNumberAccumulations(num_acc)
    #     lib.SetNumberPrescans(num_prescan)
    #     lib.SetKineticCycleTime(cycle_time)
    #     lib.SetAccumulationCycleTime(cycle_time_acc)
    #     self.acq_params["kinetics"]=(num,cycle_time,num_acc,cycle_time_acc,num_prescan)
    # def setup_fast_kinetic_mode(self, num, cycle_time_acc=0.):
    #     """
    #     Setup fast kinetic acquisition mode.
        
    #     `num` is the number of accumulated frames, `cycle_time` is the acquistion period
    #     (by default the minimal possible based on exposure and transfer time).
    #     """
    #     self._camsel()
    #     self.set_acquisition_mode("fast_kinetics")
    #     lib.SetNumberKinetics(num)
    #     lib.SetAccumulationCycleTime(cycle_time_acc)
    #     self.acq_params["fast_kinetics"]=(num,cycle_time_acc)
    # def setup_cont_mode(self, cycle_time=0):
    #     """
    #     Setup continuous acquisition mode.
        
    #     `cycle_time` is the acquistion period (by default the minimal possible based on exposure and transfer time).
    #     """
    #     self._camsel()
    #     self.set_acquisition_mode("cont")
    #     lib.SetKineticCycleTime(cycle_time)
    #     self.acq_params["cont"]=cycle_time
    # def _setup_acqusition(self, acq_mode=None, params=None):
    #     acq_mode=acq_mode or self.acq_mode
    #     params=params or self.acq_params[self.acq_mode]
    #     if acq_mode=="accum":
    #         self.setup_accum_mode(*params)
    #     elif acq_mode=="kinetics":
    #         self.setup_kinetic_mode(*params)
    #     elif acq_mode=="fast_kinetics":
    #         self.setup_fast_kinetic_mode(*params)
    #     elif acq_mode=="cont":
    #         self.setup_cont_mode(params)
    # def enable_frame_transfer_mode(self, enable=True):
    #     """
    #     Enable frame transfer mode.

    #     For description, see Andor SDK manual.
    #     """
    #     self._camsel()
    #     lib.SetFrameTransferMode(enable)
    #     self.frame_transfer_mode=enable
    # AcqTimes=collections.namedtuple("AcqTimes",["exposure","accum_cycle_time","kinetic_cycle_time"])
    # def get_timings(self):
    #     """
    #     Get acquistion timing.

    #     Return tuple ``(exposure, accum_cycle_time, kinetic_cycle_time)``.
    #     In continuous mode, the relevant cycle time is ``kinetic_cycle_time``.
    #     """
    #     self._camsel()
    #     return self.AcqTimes(*lib.GetAcquisitionTimings())
    # def get_readout_time(self):
    #     """Get frame readout time"""
    #     self._camsel()
    #     return lib.GetReadOutTime()
    # def get_keepclean_time(self):
    #     """Get sensor keep-clean time"""
    #     self._camsel()
    #     return lib.GetKeepCleanTime()

    # ### Acquisition process controls ###
    # def prepare_acquisition(self):
    #     """
    #     Prepare acquistion.
        
    #     Isn't required (called automatically on acquistion start), but decreases time required for starting acquisition later.
    #     """
    #     self._camsel()
    #     lib.PrepareAcquisition()
    # def start_acquisition(self, setup=True):
    #     """
    #     Start acquisition.

    #     If ``setup==True``, setup the acquistion parameters before the start
    #     (they don't apply automatically when the mode is changed).
    #     """
    #     self._camsel()
    #     if setup:
    #         self._setup_acqusition()
    #     lib.StartAcquisition()
    # def stop_acquisition(self):
    #     """Stop acquisition"""
    #     self._camsel()
    #     if self.get_status()=="acquiring":
    #         lib.AbortAcquisition()
    # AcqProgress=collections.namedtuple("AcqProgress",["frames_done","cycles_done"])
    # def get_progress(self):
    #     """
    #     Get acquisition progress.

    #     Return tuple ``(frames_done, cycles_done)`` (these are different in accum or kinetic mode).
    #     """
    #     self._camsel()
    #     return self.AcqProgress(*lib.GetAcquisitionProgress())
    # def wait_for_frame(self, since="lastwait", timeout=20.):
    #     """
    #     Wait for a new camera frame.

    #     `since` specifies what constitutes a new frame.
    #     Can be ``"lastread"`` (wait for a new frame after the last read frame), ``"lastwait"`` (wait for a new frame after last :func:`wait_for_frame` call),
    #     or ``"now"`` (wait for a new frame acquired after this function call).
    #     If `timeout` is exceeded, rause :exc:`AndorTimeoutError`.
    #     """
    #     funcargparse.check_parameter_range(since,"since",{"lastread","lastwait","now"})
    #     if since=="lastwait":
    #         self._camsel()
    #         if timeout is None:
    #             lib.WaitForAcquisitionByHandle(self.handle)
    #         else:
    #             try:
    #                 lib.WaitForAcquisitionByHandleTimeOut(self.handle,int(timeout*1E3))
    #             except AndorLibError as e:
    #                 if e.text_code=="DRV_NO_NEW_DATA":
    #                     raise AndorTimeoutError
    #                 else:
    #                     raise
    #     elif since=="lastread":
    #         self._camsel()
    #         while not self.get_new_images_range():
    #             self.wait_for_frame(since="lastwait",timeout=timeout)
    #     else:
    #         rng=self.get_new_images_range()
    #         last_img=rng[1] if rng else None
    #         while True:
    #             self.wait_for_frame(since="lastwait",timeout=timeout)
    #             rng=self.get_new_images_range()
    #             if rng and (last_img is None or rng[1]>last_img):
    #                 return
    # def cancel_wait(self):
    #     """Cancel wait"""
    #     self._camsel()
    #     lib.CancelWait()
    # @contextlib.contextmanager
    # def pausing_acquisition(self):
    #     """
    #     Context manager which temporarily pauses acquisition during execution of ``with`` block.

    #     Useful for applying certain settings which can't be changed during the acquisition.
    #     """
    #     acq=self.get_status()=="acquiring"
    #     try:
    #         self.stop_acquisition()
    #         yield
    #     finally:
    #         if acq:
    #             self.start_acquisition()

    # ### Image settings and transfer controls ###
    # def get_detector_size(self):
    #     """Get camera detector size (in pixels)"""
    #     self._camsel()
    #     return lib.GetDetector()
    # _read_modes=["fvb","multi_track","random_track","single_track","image"]
    # def set_read_mode(self, mode):
    #     """
    #     Set camera read mode.

    #     Can be ``"fvb"`` (average all image vertically and return it as one row), ``"single_track"`` (read a single row or several rows averaged together),
    #     ``"multi_track"`` (read multiple rows or averaged sets of rows), ``"random_track"`` (read several arbitrary lines),
    #     or ``"image"`` (read a whole image or its rectangular part).
    #     """
    #     funcargparse.check_parameter_range(mode,"mode",self._read_modes)
    #     self._camsel()
    #     lib.SetReadMode(self._read_modes.index(mode))
    #     self.read_mode=mode
    # def setup_single_track_mode(self, center, width):
    #     """
    #     Setup singe-track read mode.

    #     `center` and `width` specify selection of the rows to be averaged together.
    #     """
    #     self._camsel()
    #     lib.SetSingleTrack(center,width)
    #     self.read_params["single_track"]=(center,width)
    # def setup_multi_track_mode(self, number, height, offset):
    #     """
    #     Setup multi-track read mode.

    #     `number` is the number of rows (or row sets) to read, `height` is number of one row set (1 for a single row),
    #     `offset` is the distance between the row sets.
    #     """
    #     self._camsel()
    #     res=lib.SetMultiTrack(number,height,offset)
    #     self.read_params["multi_track"]=(number,height,offset)
    #     return res
    # def setup_random_track_mode(self, tracks):
    #     self._camsel()
    #     lib.SetRandomTracks(tracks)
    #     self.read_params["random_track"]=list(tracks)
    # def setup_image_mode(self, hstart=1, hend=None, vstart=1, vend=None, hbin=1, vbin=1):
    #     """
    #     Setup image read mode.

    #     `hstart` and `hend` specify horizontal image extent, `vstart` and `vend` specify vertical image extent
    #     (both are inclusive and starting from 1), `hbin` and `vbin` specify binning.
    #     """
    #     hdet,vdet=self.get_detector_size()
    #     hend=hdet if hend is None else hend
    #     vend=vdet if vend is None else vend
    #     hend=min(hdet,hend) # truncate the image size
    #     vend=min(vdet,vend)
    #     hend-=(hend-hstart+1)%hbin # make size divisible by bin
    #     vend-=(vend-vstart+1)%vbin
    #     lib.SetImage(hbin,vbin,hstart,hend,vstart,vend)
    #     self.read_params["image"]=(hstart,hend,vstart,vend,hbin,vbin)

    # def get_data_dimensions(self, mode=None, params=None):
    #     """Get readout data dimensions for given read mode and read parameters (current by default)"""
    #     if mode is None:
    #         mode=self.read_mode
    #     if params is None:
    #         params=self.read_params[mode]
    #     hdet,vdet=self.get_detector_size()
    #     if mode in {"fvb","single_track"}:
    #         return (1,hdet)
    #     if mode=="multi_track":
    #         return (params[0],hdet)
    #     if mode=="random_track":
    #         return (len(params),hdet)
    #     if mode=="image":
    #         (hstart,hend,vstart,vend,hbin,vbin)=params
    #         return (vend-vstart+1)//vbin,(hend-hstart+1)//hbin
    # def read_newest_image(self, dim=None, peek=False):
    #     """
    #     Read the newest image.

    #     `dim` specifies image dimensions (by default use dimensions corresponding to the current camera settings).
    #     If ``peek==True``, return the image but not mark it as read.
    #     """
    #     if dim is None:
    #         dim=self.get_data_dimensions()
    #     self._camsel()
    #     if peek:
    #         data=lib.GetMostRecentImage16(dim[0]*dim[1])
    #         return data.reshape((dim[0],dim[1])).transpose()
    #     else:
    #         rng=self.get_new_images_range()
    #         if rng:
    #             return self.read_multiple_images([rng[1],rng[1]],dim=dim)[0,:,:]
    # def read_oldest_image(self, dim=None):
    #     """
    #     Read the oldest un-read image in the buffer.

    #     `dim` specifies image dimensions (by default use dimensions corresponding to the current camera settings).
    #     """
    #     if dim is None:
    #         dim=self.get_data_dimensions()
    #     self._camsel()
    #     data=lib.GetOldestImage16(dim[0]*dim[1])
    #     return data.reshape((dim[0],dim[1])).transpose()
    # def get_ring_buffer_size(self):
    #     """Get the size of the image ring buffer"""
    #     self._camsel()
    #     return lib.GetSizeOfCircularBuffer()
    # def get_new_images_range(self):
    #     """
    #     Get the range of the new images.
        
    #     Return tuple ``(first, last)`` with images range (inclusive).
    #     If no images are available, return ``None``.
    #     """
    #     self._camsel()
    #     try:
    #         return lib.GetNumberNewImages()
    #     except AndorLibError as e:
    #         if e.text_code=="DRV_NO_NEW_DATA":
    #             return None
    #         raise
    # def read_multiple_images(self, rng=None, dim=None):
    #     """
    #     Read multiple images specified by `rng` (by default, all un-read images).

    #     `dim` specifies images dimensions (by default use dimensions corresponding to the current camera settings).
    #     """
    #     self._camsel()
    #     if rng is None:
    #         rng=self.get_new_images_range()
    #     if dim is None:
    #         dim=self.get_data_dimensions()
    #     if rng is None:
    #         return np.zeros((0,dim[1],dim[0]))
    #     data,vmin,vmax=lib.GetImages16(rng[0],rng[1],dim[0]*dim[1]*(rng[1]-rng[0]+1))
    #     return np.transpose(data.reshape((-1,dim[0],dim[1])),axes=[0,2,1])

    # def flush_buffer(self):
    #     """Flush the camera buffer (restart the acquistion)"""
    #     acq_mode=self.acq_mode
    #     if acq_mode=="cont":
    #         self.set_acquisition_mode("single")
    #     else:
    #         self.set_acquisition_mode("cont")
    #     self.prepare_acquisition()
    #     self.set_acquisition_mode(acq_mode)
    #     self.prepare_acquisition()

    # ### Combined functions ###
    # def snap(self):
    #     """Snap a single image (with preset image read mode parameters)"""
    #     self.set_acquisition_mode("single")
    #     self.set_read_mode("image")
    #     self.start_acquisition()
    #     self.wait_for_frame()
    #     self.stop_acquisition()
    #     return self.read_newest_image()