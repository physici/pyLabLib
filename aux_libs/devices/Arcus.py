from .misc import default_lib_folder, load_lib

import os.path
import ctypes
import time

class ArcusError(RuntimeError):
    """Generic Arcus error."""

class PerformaxStage(object):
    """
    Performax translational stage.
    """
    def __init__(self, lib_path=None, idx=0):
        object.__init__(self)
        if lib_path is None:
            lib_path=os.path.join(default_lib_folder,"PerformaxCom.dll")
        self.dll=load_lib(lib_path,locally=True)
        self.dll.fnPerformaxComOpen.argtypes=[ctypes.c_uint32,ctypes.POINTER(ctypes.c_uint64)]
        self.dll.fnPerformaxComClose.argtypes=[ctypes.c_uint64]
        self.dll.fnPerformaxCommandReply.argtypes=[ctypes.c_uint64,ctypes.c_char_p,ctypes.c_char_p]
        self.dll.fnPerformaxComGetProductString.argtypes=[ctypes.c_uint32,ctypes.c_char_p,ctypes.c_uint32]
        self.idx=idx
        self.handle=None
        self.rbuff=ctypes.create_string_buffer(65536)
        self.open()
        self.set_absolute_mode()
        self.enable_all_outputs()

    def open(self):
        if self.handle:
            self.close()
        self.handle=ctypes.c_uint64()
        for _ in range(5):
            if self.dll.fnPerformaxComOpen(self.idx,ctypes.byref(self.handle)):
                return
            time.sleep(0.3)
        raise ArcusError("can't connect to the stage with index {}".format(self.idx))
    def close(self):
        if self.handle:
            for _ in range(5):
                if self.dll.fnPerformaxComClose(self.handle):
                    self.handle=None
                    return
                time.sleep(0.3)
            raise ArcusError("can't disconnect from the stage with index {}".format(self.idx))
    def _check_handle(self):
        if not self.handle:
            raise ArcusError("device is not opened")

    def get_device_id(self):
        devs=[]
        for n in range(5):
            if not self.dll.fnPerformaxComGetProductString(self.idx,self.rbuff,n):
                raise ArcusError("can't get info for the device with index {}".format(self.idx))
            devs.append(self.rbuff.value)
        return devs
    def query(self, comm):
        self._check_handle()
        if self.dll.fnPerformaxCommandReply(self.handle,comm,self.rbuff):
            return self.rbuff.value
        else:
            raise ArcusError("error sending command {}".format(comm))

    @staticmethod
    def _check_axis(axis):
        if axis.lower() not in ["x","y","z","u"]:
            raise ArcusError("unrecognized axis: {}".format(axis))
        return axis.upper()

    def set_absolute_mode(self):
        self.query("ABS")
    def enable_output(self, axis, enable=True):
        axis=self._check_axis(axis)
        axisn="XYZU".index(axis)+1
        self.query("EO{}={}".format(axisn,"1" if enable else "0"))
    def enable_all_outputs(self, enable=True):
        self.query("EO={}".format("15" if enable else "0"))

    def get_pos(self, axis):
        axis=self._check_axis(axis)
        return int(self.query("P"+axis))
    def set_pos_reference(self, axis, pos):
        axis=self._check_axis(axis)
        self.query("P{}={:d}".format(axis,pos))
    def move(self, axis, pos):
        axis=self._check_axis(axis)
        self.query("{}{:d}".format(axis,pos))
    def jog(self, axis, direction):
        axis=self._check_axis(axis)
        if not direction: # 0 or False also mean left
            direction="-"
        if direction in [1, True]:
            direction="+"
        if direction not in ["+","-"]:
            raise ArcusError("unrecognized direction: {}".format(direction))
        self.query("J{}{}".format(axis,direction))
    def stop(self, axis):
        axis=self._check_axis(axis)
        self.query("STOP"+axis)
    def stop_all(self):
        for axis in "XYZU":
            self.query("STOP"+axis)

    def get_speed(self):
        return int(self.query("HS"))
    def set_speed(self, speed):
        self.query("HS={:d}".format(speed))

    _status_bits={  "accel":0x001,"decel":0x002,"moving":0x004,
                    "alarm":0x008,
                    "sw_plus_lim":0x010,"sw_minus_lim":0x020,"sw_home":0x040,
                    "err_plus_lim":0x080,"err_minus_lim":0x100,"err_alarm":0x200,
                    "TOC_timeout":0x800}
    def _get_status(self):
        stat=self.query("MST")
        return [int(x) for x in stat.split(":") if x]
    def get_axis_status_n(self, axis):
        axis=self._check_axis(axis)
        axis_n="XYZU".index(axis)
        return self._get_status()[axis_n]
    def get_axis_status(self, axis):
        statn=self.get_axis_status_n(axis)
        return set([ k for k in self._status_bits if self._status_bits[k]&statn ])
    def is_moving(self, axis):
        return self.get_axis_status_n(axis)&0x007

    def check_limit_error(self, axis):
        stat=self.get_axis_status_n(axis)
        err=""
        if stat&self._status_bits["err_plus_lim"]:
            err=err+"+"
        if stat&self._status_bits["err_minus_lim"]:
            err=err+"-"
        return err
    def clear_limit_error(self, axis):
        axis=self._check_axis(axis)
        self.query("CLR"+axis)
