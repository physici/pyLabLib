from ...core.utils import general

from .misc import default_lib_folder, load_lib

import os.path
import ctypes
import time

class SmarActError(RuntimeError):
    """Generic SmarAct error."""

class SCU3D(object):
    """
    SCU3D translational stage.
    """
    def __init__(self, lib_path=None, idx=0, channel_mapping="xyz", channel_dir="+++"):
        object.__init__(self)
        if lib_path is None:
            lib_path=os.path.join(default_lib_folder,"SCU3DControl.dll")
        self.dll=load_lib(lib_path)
        self.dll.SA_MoveStep_S.argtypes=[ctypes.c_uint,ctypes.c_uint,ctypes.c_int,ctypes.c_uint,ctypes.c_uint]
        self.dll.SA_GetStatus_S.argtypes=[ctypes.c_uint,ctypes.c_uint,ctypes.POINTER(ctypes.c_uint)]
        self.idx=idx
        self.channel_mapping=channel_mapping
        self.channel_dir=channel_dir
        self.open()

    def open(self):
        self._check_status("SA_InitDevices",self.dll.SA_InitDevices(0))
    def close(self):
        self._check_status("SA_ReleaseDevices",self.dll.SA_ReleaseDevices())

    _func_status={  0:"SA_OK",
                    1:"SA_INITIALIZATION_ERROR",
                    2:"SA_NOT_INITIALIZED_ERROR",
                    3:"SA_NO_DEVICES_FOUND_ERROR",
                    4:"SA_TOO_MANY_DEVICES_ERROR",
                    5:"SA_INVALID_DEVICE_INDEX_ERROR",
                    6:"SA_INVALID_CHANNEL_INDEX_ERROR",
                    7:"SA_TRANSMIT_ERROR",
                    8:"SA_WRITE_ERROR",
                    9:"SA_INVALID_PARAMETER_ERROR",
                    10:"SA_READ_ERROR",
                    12:"SA_INTERNAL_ERROR",
                    13:"SA_WRONG_MODE_ERROR",
                    14:"SA_PROTOCOL_ERROR",
                    15:"SA_TIMEOUT_ERROR",
                    16:"SA_NOTIFICATION_ALREADY_SET_ERROR",
                    17:"SA_ID_LIST_TOO_SMALL_ERROR",
                    18:"SA_DEVICE_ALREADY_ADDED_ERROR",
                    19:"SA_DEVICE_NOT_FOUND_ERROR",
                    128:"SA_INVALID_COMMAND_ERROR",
                    129:"SA_COMMAND_NOT_SUPPORTED_ERROR",
                    130:"SA_NO_SENSOR_PRESENT_ERROR",
                    131:"SA_WRONG_SENSOR_TYPE_ERROR",
                    132:"SA_END_STOP_REACHED_ERROR",
                    133:"SA_COMMAND_OVERRIDDEN_ERROR",
                    134:"SA_HV_RANGE_ERROR",
                    135:"SA_TEMP_OVERHEAT_ERROR",
                    136:"SA_CALIBRATION_FAILED_ERROR",
                    137:"SA_REFERENCING_FAILED_ERROR",
                    138:"SA_NOT_PROCESSABLE_ERROR",
                    255:"SA_OTHER_ERROR"}
    def _check_status(self, func, status):
        if status:
            if status in self._func_status:
                raise SmarActError("function {} raised error: {} ({})".format(func,status,self._func_status[status]))
            else:
                raise SmarActError("function {} raised unknown error: {}".format(func,status))
    
    def _get_channel(self, channel):
        if channel in list(self.channel_mapping):
            return self.channel_mapping.find(channel)
        return channel
    def move(self, channel, steps, voltage, frequency):
        channel=self._get_channel(channel)
        channel_dir=-1 if self.channel_dir[channel]=="-" else 1
        stat=self.dll.SA_MoveStep_S(self.idx,self._get_channel(channel),int(steps)*channel_dir,int(voltage*10),int(frequency))
        self._check_status("SA_MoveStep_S",stat)
    _simple_move_settings=[ (1,25.3,1E3), (1,28,1E3), (1,32,1E3), (1,38,1E3), (1,47,1E3),
                            (1,60.5,1E3), (1,80.8,1E3), (2,65.6,1E3), (2,88.4,1E3), (4,88.4,1E3),
                            (7,100.,1E3), (14,100.,1E3), (28,100.,1E3), (56,100.,1.1E3), (100,100.,2.2E3), 
                            (200,100.,4.4E3), (400,100.,8.8E3), (1E3,100.,10E3), (1.8E3,100.,10E3)]
    def move_simple(self, channel, speed, steps=1):
        par=self._simple_move_settings[max(speed-1,0)]
        step_dir=1 if steps>0 else -1
        for _ in range(abs(steps)):
            self.move(channel,par[0]*step_dir,par[1],par[2])
            self.wait_status(channel)

    _chan_status={  0:"stopped",
                    1:"setting_amplitude",
                    2:"moving",
                    3:"targeting",
                    4:"holding",
                    5:"calibrating",
                    6:"moving_to_reference"}
    def get_status(self, channel):
        val=ctypes.c_uint()
        stat=self.dll.SA_GetStatus_S(self.idx,self._get_channel(channel),ctypes.byref(val))
        self._check_status("SA_GetStatus_S",stat)
        if val.value in self._chan_status:
            return self._chan_status[val.value]
        else:
            raise SmarActError("function SA_GetStatus_S returned unknown status: {}".format(val.value))
    def wait_status(self, channel, status="stopped", timeout=3.):
        countdown=general.Countdown(timeout)
        while True:
            cur_status=self.get_status(channel)
            if cur_status==status:
                return
            if countdown.passed():
                raise SmarActError("status waiting timed out")
            time.sleep(1E-2)