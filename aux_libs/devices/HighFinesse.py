from .misc import default_lib_folder, load_lib

import os.path
import ctypes


class WS7Error(RuntimeError):
    """WS/7 wavemeter error."""

class WS7(object):
    """
    WS/7 precision wavemeter.
    """
    def __init__(self, lib_path=None, idx=0):
        object.__init__(self)
        if lib_path is None:
            lib_path=os.path.join(default_lib_folder,"wlmData.dll")
        self.dll=load_lib(lib_path)
        self.dll.GetFrequencyNum.restype=ctypes.c_double
        self.dll.GetFrequencyNum.argtypes=[ctypes.c_long,ctypes.c_double]
        self.idx=idx
    
    _GetFrequencyNum_err={  0:"ErrNoValue: No value",
                            -1:"ErrNoSignal: No signal detected",
                            -2:"ErrBadSignal: No calculable signal detected",
                            -3:"ErrLowSignal: Signal too small / underexposed",
                            -4:"ErrBigSignal: Signal too big / overexposed",
                            -5:"ErrWlmMissing: Wavelength meter is not active", 
                            -6:"ErrNotAvailable: Function is not available", 
                            -8:"ErrNoPulse: Signal can't be separated into pulses", 
                            -7:"InfNothingChanged",
                            -13:"ErrDiv0", 
                            -14:"ErrOutOfRange", 
                            -15:"ErrUnitNotAvaliable"}
    def get_frequency(self):
        res=self.dll.GetFrequencyNum(self.idx,0.)
        if int(res)<=0:
            err=int(res)
            if err in self._GetFrequencyNum_err:
                raise WS7Error("GetFrequencyNum returned error: {} ({})".format(err,self._GetFrequencyNum_err[err]))
            else:
                raise WS7Error("GetFrequencyNum returned unknown error: {}".format(err))
        return res*1E12