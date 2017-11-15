from ..datatable import wrapping #@UnresolvedImport

import platform
import numpy as np

arch=platform.architecture()

if arch[0]=="32bit":
    from iir_transform_32 import iir_apply
elif arch[0]=="64bit":
    from iir_transform_64 import iir_apply
else:
    raise ImportError("Unexpected system architecture: {0}".format(arch))

def iir_apply_complex(trace, xcoeff, ycoeff):
    """
    Wrapper for :func:`iir_apply` function that accounts for the trace being possibly complex (coefficients still have to be real)
    and for datatable types.
    """
    wrap=wrapping.wrap(trace)
    trace=np.asarray(trace)
    if np.iscomplexobj(trace):
        return wrap.array_replaced(iir_apply(trace.real,xcoeff,ycoeff)+1j*iir_apply(trace.imag,xcoeff,ycoeff),wrapped=False)
    else:
        return wrap.array_replaced(iir_apply(trace,xcoeff,ycoeff),wrapped=False)