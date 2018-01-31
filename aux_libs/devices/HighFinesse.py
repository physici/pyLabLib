from .misc import default_lib_folder, load_lib

import os.path
import ctypes


class HFError(RuntimeError):
    """Generic HighFinesse wavemeter error."""

class WS(object):
    """
    WS precision wavemeter.
    """
    def __init__(self, lib_path=None, idx=0):
        object.__init__(self)
        if lib_path==6:
            lib_path=os.path.join(default_lib_folder,"wlmData6.dll")
        if lib_path in [None,7]:
            lib_path=os.path.join(default_lib_folder,"wlmData7.dll")
        self.dll=load_lib(lib_path)
        self.dll.GetFrequencyNum.restype=ctypes.c_double
        self.dll.GetFrequencyNum.argtypes=[ctypes.c_long,ctypes.c_double]
        self.idx=idx

    def open(self):
        pass
    def close(self):
        pass

    def __enter__(self):
        return self
    def __exit__(self, *args, **vargs):
        return False
    
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
    def get_frequency(self, return_exp_error=True):
        res=self.dll.GetFrequencyNum(self.idx,0.)
        if int(res)<=0:
            err=int(res)
            if return_exp_error:
                if err==-3:
                    return "under"
                if err==-4:
                    return "over"
            if err in self._GetFrequencyNum_err:
                raise HFError("GetFrequencyNum returned error: {} ({})".format(err,self._GetFrequencyNum_err[err]))
            else:
                raise HFError("GetFrequencyNum returned unknown error: {}".format(err))
        return res*1E12