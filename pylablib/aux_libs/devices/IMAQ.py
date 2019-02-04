from ...core.utils import dictionary, py3, general
from ...core.devio import data_format, interface
from ...core.dataproc import image as image_utils

import numpy as np
import contextlib
import time
import collections
import ctypes


from . import IMAQ_lib
lib=IMAQ_lib.lib
try:
    lib.initlib()
except (ImportError, OSError):
    pass
IMAQError=IMAQ_lib.IMAQLibError
class IMAQGenericError(RuntimeError):
    "Generic IMAQ camera error."
class IMAQTimeoutError(IMAQGenericError):
    "Timeout while waiting."

_depends_local=[".IMAQ_lib","...core.devio.interface"]



def list_cameras():
    """List all cameras available through IMAQ interface"""
    cameras=[]
    i=0
    try:
        while Ture:
            if_name=lib.imgInterfaceQueryNames(i)
            cameras.append(py3.as_str(if_name))
            i+=1
    except IMAQError:
        pass
    return cameras


class IMAQCamera(interface.IDevice):
    """
    Generic IMAQ camera interface.

    Args:
        name: interface name (can be learned by :func:`list_cameras`; usually, but not always, starts with ``"cam"``)
    """
    def __init__(self, name="img0"):
        interface.IDevice.__init__(self)
        self.init_done=False
        self.name=name
        self.ifid=None
        self.sid=None
        self.open()
        self.image_indexing="rct"
        self._buffers=[]
        self._last_read_frame=None
        self._start_acq_count=None
        self._last_wait_frame=None
        self._lost_frames=None
        self._acq_params=None
        self.post_open()
        self.init_done=True

        self._add_full_info_node("model_data",self.get_model_data)
        self._add_full_info_node("interface_name",lambda: self.name)
        self._add_status_node("buffer_size",lambda: self.buffer_status().size)
        self._add_status_node("buffer_status",self.buffer_status)
        self._add_status_node("data_dimensions",self.get_data_dimensions)
        self._add_full_info_node("detector_size",self.get_detector_size)
        self._add_settings_node("roi",self.get_roi,self.set_roi)
        self._add_status_node("roi_limits",self.get_roi_limits)

        
    def open(self):
        """Open connection to the camera"""
        self.ifid=lib.imgInterfaceOpen(self.name)
        self.sid=lib.imgSessionOpen(self.ifid)
        self.post_open()
    def close(self):
        """Close connection to the camera"""
        if self.sid is not None:
            lib.imgClose(self.sid)
            self.sid=None
            lib.imgClose(self.ifid)
            self.ifid=None
    def reset(self):
        """Reset connection to the camera"""
        if self.ifid is not None:
            lib.imgClose(self.sid)
            self.sid=None
            lib.imgInterfaceReset(self.ifid)
            self.sid=lib.imgSessionOpen(self.ifid)
    def is_opened(self):
        """Check if the device is connected"""
        return self.sid is not None

    def post_open(self):
        """Action to automatically call on opening"""
        pass

    def _norm_attr(self, attr):
        if attr not in IMAQ_lib.IMAQ_attrs_inv and ("IMG_ATTR_"+attr) in IMAQ_lib.IMAQ_attrs_inv:
            return "IMG_ATTR_"+attr
        return attr
    def get_int_value(self, attr, default=None):
        """Get value of an integer attribute with a given name"""
        try:
            return lib.imgGetAttribute_uint32(self.sid,self._norm_attr(attr))
        except IMAQError as e:
            if default is None:
                raise e from None
            return default
    def set_int_value(self, attr, value):
        """Set value of an integer attribute with a given name"""
        lib.imgSetAttribute2_uint32(self.sid,self._norm_attr(attr),value)
        return lib.imgGetAttribute_uint32(self.sid,self._norm_attr(attr))
    def get_float_value(self, attr, default=None):
        """Get value of a floating point attribute with a given name"""
        try:
            return lib.imgGetAttribute_double(self.sid,self._norm_attr(attr))
        except IMAQError as e:
            if default is None:
                raise e from None
            return default
    def get_float_value(self, attr):
        """Set value of a floating point attribute with a given name"""
        lib.imgSetAttribute2_double(self.sid,self._norm_attr(attr),value)
        return lib.imgGetAttribute_double(self.sid,self._norm_attr(attr))
    
    ModelData=collections.namedtuple("ModelData",["serial"])
    def get_model_data(self):
        """
        Get camera model data.

        Return tuple ``(serial,)``.
        """
        serial=self.get_int_value("GETSERIAL")
        return self.ModelData(serial)

    def _get_data_dimensions_rc(self):
        return self.get_int_value("ROI_HEIGHT"),self.get_int_value("ROI_WIDTH")
    def get_data_dimensions(self):
        """Get the current data dimension (taking ROI and binning into account)"""
        return image_utils.convert_shape_indexing(self._get_data_dimensions_rc(),"rc",self.image_indexing)
    def get_detector_size(self):
        """Get camera detector size (in pixels) as a tuple ``(width, height)``"""
        _,_,mw,mh=lib.imgSessionFitROI(self.sid,0,0,0,2**31-1,2**31-1)
        return mw,mh
    def get_roi(self):
        """
        Get current ROI.

        Return tuple ``(hstart, hend, vstart, vend)``.
        """
        t,l,h,w=lib.imgSessionGetROI(self.sid)
        return l,t,l+w,t+h
    def set_roi(self, hstart=0, hend=None, vstart=0, vend=None):
        """
        Setup camera ROI.

        By default, all non-supplied parameters take extreme values.
        """
        
        det_size=self.get_detector_size()
        if hend is None:
            hend=det_size[0]
        if vend is None:
            vend=det_size[1]
        fit_roi=lib.imgSessionFitROI(self.sid,0,vstart,hstart,max(vend-vstart,1),max(hend-hstart,1))
        with self.pausing_acquisition():
            lib.imgSessionConfigureROI(self.sid,*fit_roi)
        return self.get_roi()
    def get_roi_limits(self):
        """
        Get the minimal and maximal ROI parameters.

        Return tuple ``(min_roi, max_roi)``, where each element is in turn 4-tuple describing the ROI.
        """
        minp=lib.imgSessionFitROI(self.sid,0,0,0,1,1)
        detsize=self.get_detector_size()
        min_roi=(0,0)+minp[2:]
        max_roi=(detsize[0]-minp[2],detsize[1]-minp[3])+detsize
        return (min_roi,max_roi)
    


    def _get_ctypes_buffer(self):
        if self._buffers:
            buffs=(ctypes.c_char_p*len(self._buffers))()
            for i,b in enumerate(self._buffers):
                buffs[i]=b
            return buffs
        else:
            return None
    def _deallocate_buffers(self):
        if self._buffers:
            for b in self._buffers:
                lib.imgDisposeBuffer(b)
        self._buffers=[]
        self._last_read_frame=None
        self._start_acq_count=None
        self._lost_frames=None
    def _allocate_buffers(self, n):
        self._deallocate_buffers()
        buffer_size=self._get_buffer_size()
        for _ in range(n):
            b=lib.imgCreateBuffer(self.sid,0,buffer_size)
            self._buffers.append(b)
    @contextlib.contextmanager
    def _reset_buffers(self):
        nframes=len(self._buffers)
        self._deallocate_buffer()
        try:
            yield
        finally:
            if nframes:
                self._allocate_buffer(nframes)
    def _acquired_frames(self):
        if self._start_acq_count is None:
            return 0
        return self.get_int_value("FRAME_COUNT",0)-self._start_acq_count
    def _get_buffer_num(self, frame):
        if not self._buffers:
            return -1
        return (frame+self._start_acq_count)%len(self._buffers)
        


    def setup_acqusition(self, continuous, frames):
        """
        Setup acquisition mode.

        `continuous` determines whether acquisition runs continuously, or stops after the given number of frames
        (note that :meth:`acquision_in_progress` would still return ``True`` in this case, even though new frames are no longer acquired).
        `frames` sets up number of frame buffers.
        If ``start==True``, start acqusition directly after setup.
        """
        self._allocate_buffers(frames)
        cbuffs=self._get_ctypes_buffer()
        if continuous:
            lib.imgRingSetup(self.sid,len(self._buffers),cbuffs,0,0)
        else:
            skips=(ctypes.c_uint32*frames)(0)
            lib.imgSequenceSetup(self.sid,len(self._buffers),cbuffs,skips,0,0)
        self._acq_params=(continuous,frames)
        self._last_read_frame=-1
        self._start_acq_count=0
        self._lost_frames=0
        self._last_wait_frame=-1
    def clear_acquisition(self):
        """Clear all acquisition details and free all buffers"""
        self.stop_acquisition()
        lib.imgSessionAbort(self.sid)
        self._deallocate_buffers()
    def start_acquisition(self):
        """Start acquistion"""
        self.stop_acquisition()
        if self._acq_params is None:
            self.setup_acqusition(True,100)
        self._start_acq_count=self.get_int_value("FRAME_COUNT",0)
        self._last_read_frame=-1
        self._lost_frames=0
        lib.imgSessionStartAcquisition(self.sid)
    def stop_acquisition(self):
        """Stop acquistion"""
        lib.imgSessionStopAcquisition(self.sid)
        self._last_wait_frame=-1
    def acquision_in_progress(self):
        """Check if acquisition is in progress"""
        return bool(lib.imgSessionStatus(self.sid)[0])
    
    @contextlib.contextmanager
    def pausing_acquisition(self):
        """
        Context manager which temporarily pauses acquisition during execution of ``with`` block.

        Useful for applying certain settings which can't be changed during the acquisition (e.g., ROI or bit depth).
        """
        acq_params=self._acq_params
        acq_in_progress=self.acquision_in_progress()
        try:
            self.clear_acquisition()
            yield
        finally:
            if acq_params:
                self.setup_acqusition(*acq_params)
            if acq_in_progress:
                self.start_acquisition()

    TBufferStatus=collections.namedtuple("TBufferStatus",["unread","lost","size"])
    def buffer_status(self):
        """
        Get buffer fill status.

        Return tuple ``(unread, lost, size)``, where ``unread`` is the number of acquired but not read frames,
        ``lost`` is the number of lost (written over) frames and ``size`` is the total buffer size (in frames).
        """
        rng=self.get_new_images_range()
        unread=0 if rng is None else rng[1]-rng[0]+1
        buff_size=len(self._buffers)
        if rng is not None:
            lost_frames=self._lost_frames+max(0,rng[1]-buff_size-self._last_read_frame)
        else:
            lost_frames=0
        return self.TBufferStatus(unread,lost_frames,buff_size)
    def get_new_images_range(self):
        """
        Get the range of the new images.
        
        Return tuple ``(first, last)`` with images range (inclusive).
        If no images are available, return ``None``.
        """
        frame_cnt=self._acquired_frames()
        if not self._buffers or frame_cnt<=0:
            return None
        if self._last_read_frame+1>=frame_cnt:
            return None
        buff_size=len(self._buffers)
        if self._last_read_frame<frame_cnt-buff_size:
            return (frame_cnt-buff_size,frame_cnt-1)
        return (self._last_read_frame+1,frame_cnt-1)
    def wait_for_frame(self, since="lastread", timeout=20.):
        """
        Wait for a new camera frame.

        `since` specifies what constitutes a new frame.
        Can be ``"lastread"`` (wait for a new frame after the last read frame),
        ``"lastwait"`` (wait for a new frame after last :func:`wait_for_frame` call),
        or ``"now"`` (wait for a new frame acquired after this function call).
        If `timeout` is exceeded, raise :exc:`IMAQdxError`.
        `period` specifies camera polling period.
        """
        if not self.acquision_in_progress():
            return
        last_acq_frame=self._acquired_frames()-1
        if since=="lastread" and last_acq_frame>self._last_read_frame:
            self._last_wait_frame=last_acq_frame
            return
        if since=="lastwait" and last_acq_frame>self._last_wait_frame:
            self._last_wait_frame=acq_flast_acq_framerames
            return
        try:
            lib.imgSessionWaitSignal2(self.sid,4,11,0,int(timeout*1000))
        except IMAQError as e:
            if e.name=="IMG_ERR_TIMEOUT":
                raise IMAQTimeoutError() from None
            elif e.name=="IMG_ERR_BOARD_NOT_RUNNING" and not self.acquision_in_progress():
                pass
            else:
                raise e from None
        self._last_wait_frame=self._acquired_frames()-1
        return
        

    def _read_data_raw(self, size_bytes, buffer_num=0):
        """Return raw bytes string from the given buffer number"""
        return ctypes.string_at(self._buffers[buffer_num],size_bytes)
    
    def _get_buffer_bpp(self):
        return self.get_int_value("BYTESPERPIXEL",1)
    def _get_buffer_dtype(self):
        bpp=self.get_int_value("BYTESPERPIXEL",1)
        return "<u{}".format(self._get_buffer_bpp())
    def _get_buffer_size(self):
        bpp=self._get_buffer_bpp()
        roi=self.get_roi()
        w,h=roi[1]-roi[0],roi[3]-roi[2]
        return w*h*bpp
    def _parse_buffer(self, buffer):
        r,c=self._get_data_dimensions_rc()
        bpp=self.get_int_value("BYTESPERPIXEL",1)
        if len(buffer)!=r*c*bpp:
            raise ValueError("wrong buffer size: expected {}x{}x{}={}, got {}".format(r,c,bpp,r*c*bpp,len(buffer)))
        dt="<u{}".format(bpp)
        return np.frombuffer(buffer,dtype=dt).reshape((r,c))
    def _read_multiple_images_raw(self, size_bytes, rng=None, peek=False, missing_frame="skip"):
        """
        Read multiple images specified by `rng` (by default, all un-read images).

        If ``peek==True``, return images but not mark them as read.
        `missing_frame` determines what to do with frames which are out of range (missing or lost):
        can be ``"none"`` (replacing them with ``None``), ``"zero"`` (same as ``None``, added for comaptibility with :func:`read_multiple_images`),
        or ``"skip"`` (skipping them).
        """
        if not self._buffers:
            return None
        last_acq_frame=self._acquired_frames()-1
        last_valid_buffer=last_acq_frame-len(self._buffers)
        if rng is None:
            rng=self.get_new_images_range()
        if rng[1]<last_valid_buffer:
            read_rng=0,-1
        else:
            read_rng=max(rng[0],last_valid_buffer),rng[1]
        raw_frames=[self._read_data_raw(size_bytes,self._get_buffer_num(n)) for n in range(read_rng[0],read_rng[1]+1)]
        if missing_frame=="none":
            raw_frames=[None]*(rng[1]-rng[0]-len(raw_frames))+raw_frames
        if not peek:
            if rng[1]>self._last_read_frame:
                passed_frames=rng[1]-self._last_read_frame
                read_frames=read_rng[1]-read_rng[0]+1
                if passed_frames>read_frames:
                    self._lost_frames+=passed_frames-read_frames
                self._last_read_frame=rng[1]
        return raw_frames
    def read_multiple_images(self, rng=None, peek=False, missing_frame="skip"):
        """
        Read multiple images specified by `rng` (by default, all un-read images).

        If ``peek==True``, return images but not mark them as read.
        `missing_frame` determines what to do with frames which are out of range (missing or lost):
        can be ``"none"`` (replacing them with ``None``), ``"zero"`` (replacing them with zero-filled frame),
        or ``"skip"`` (skipping them).
        """
        img_size=self._get_buffer_size()
        raw_data=self._read_multiple_images_raw(img_size,rng=rng,peek=peek,missing_frame=missing_frame)
        if raw_data is None:
            return None
        parsed_data=[(self._parse_buffer(b) if b is not None else None) for b in raw_data]
        if missing_frame=="zero":
            dt=self._get_buffer_dtype()
            parsed_data=[(np.zeros(img_size,dtype=dt) if f is None else f) for f in parsed_data]
        return [(None if f is None else image_utils.convert_image_indexing(f,"rct",self.image_indexing)) for f in parsed_data]

    def snap(self, timeout=20.):
        """Snap a single image (with preset image read mode parameters)"""
        return self.grab(1,frame_timeout=timeout)[0]

    def grab(self, n, buff_frames=5000, frame_timeout=20., missing_frame="none", return_buffer_status=False):
        """
        Snap `n` images (with preset image read mode parameters)
        
        `buff_frames` determines buffer size.
        Timeout is specified for a single-frame acquisition, not for the whole acquisition time.
        `missing_frame` determines what to do with frames which have been lost:
        can be ``"none"`` (replacing them with ``None``), ``"zero"`` (replacing them with zero-filled frame),
        or ``"skip"`` (skipping them, while still keeping total frames number to `n`).
        """
        buff_frames=min(n,buff_frames)
        frames=[]
        self.setup_acqusition(1 if buff_frames<n else 0,buff_frames)
        self.start_acquisition()
        try:
            while len(frames)<n:
                self.wait_for_frame(timeout=frame_timeout)
                frames+=self.read_multiple_images(missing_frame=missing_frame)
            return (frames[:n],self.buffer_status()) if return_buffer_status else frames[:n]
        finally:
            self.clear_acquisition()