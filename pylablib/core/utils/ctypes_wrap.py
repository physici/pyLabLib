from . import functions
from ..devio import data_format
from .funcargparse import getdefault

import numpy as np

import ctypes
import collections

def _default_argnames(argtypes):
    return ["arg{}".format(i+1) for i in range(len(argtypes))]

def _get_value(rval):
	try:
		return rval.value
	except AttributeError:
		return rval

def setup_func(func, argtypes, restype=None, errcheck=None):
    """
    Setup a ctypes function.

    Assign argtypes (list of argument types), restype (return value type) and errcheck (error checking function called for the return value).
    """
    func.argtypes=argtypes
    if restype is not None:
        func.restype=restype
    if errcheck is not None:
        func.errcheck=errcheck

class CTypesWrapper(object):
    """
    Wrapper object for ctypes function.

    Cosntructor argumetns coincide with the call arguments, and determine their default values.
    For their meaning, see :meth:`wrap`.
    """
    def __init__(self, argtypes=None, argnames=None, restype=None, return_res="auto", rvprep=None, rvconv=None, rvref=None, rvnames=None, tuple_single_retval=False, errcheck=None):
        object.__init__(self)
        self.argtypes=getdefault(argtypes,[])
        self.argnames=argnames
        self.restype=restype
        self.errcheck=errcheck
        self.rvconv=rvconv
        self.rvnames=rvnames
        self.rvprep=rvprep
        self.rvref=rvref
        self.return_res=return_res
        self.tuple_single_retval=tuple_single_retval
    
    @staticmethod
    def _default_names(pref, n):
        return ["{}{}".format(pref,i+1) for i in range(n)]
    @staticmethod
    def _get_value(rval):
        try:
            return rval.value
        except AttributeError:
            return rval
    @staticmethod
    def _prep_rval(argtypes, rvprep, args):
        if rvprep is None:
            rvprep=[None]*len(argtypes)
        return [t() if p is None else p(*args) for (t,p) in zip(argtypes,rvprep)]
    @staticmethod
    def _conv_rval(rvals, rvconv, args):
        if rvconv is None:
            rvconv=[None]*len(rvals)
        return [CTypesWrapper._get_value(v) if c is None else c(v,*args) for (v,c) in zip(rvals,rvconv)]
    @staticmethod
    def _split_args(argnames):
        iargs=[i for i,n in enumerate(argnames) if n is not None]
        irvals=[i for i,n in enumerate(argnames) if n is None]
        return iargs,irvals
    @staticmethod
    def _join_args(iargs, args, irvals, rvals):
        vals=[None]*(len(args)+len(rvals))
        for i,a in zip(iargs,args):
            vals[i]=a
        for i,rv in zip(irvals,rvals):
            vals[i]=rv
        return vals
    @staticmethod
    def _wrap_rvals(res, rvals, rvnames, return_res):
        if isinstance(return_res,tuple):
            return_res,res_pos=return_res
        else:
            res_pos=0
        if return_res:
            rvals[res_pos:res_pos]=res
            if rvnames is not None:
                rvnames[res_pos:res_pos]="return_value"
        if rvnames is None:
            return tuple(rvals)
        else:
            return collections.namedtuple("Result",rvnames)(*rvals)

    def wrap(self, func, argtypes=None, argnames=None, restype=None, return_res=None, rvprep=None, rvconv=None, rvref=None, rvnames=None, tuple_single_retval=None, errcheck=None):
        """
        Wrap C function in a Python call.

        Args:
            func: C function
            argtypes (list): list of `func` argument types;
                if an argument is of return-by-pointer kind, it should be the value type (the pointer is added automatically)
            argnames (list): list of argument names of the function. Includes either strings (which are interpreted as argument names passed to the wrapper function),
                or ``None`` (whcih mean that this argument is return-by-pointer).
            restype: type of the return value. Can be ``None`` if the return value isn't used.
            return_res (bool): determines whether return the function return value. By default, it is returned only if there are no return-by-pointer arguments.
            rvprep (list): list of functions which prepare return-by-pointer arguments before passing them to the function.
                By default, these are standard ctypes initializer for the corresponding types (usually equivalent to zero).
            rvconv (list): list of functions which convert the return-by-pointer values after the function call.
                By default, simply get the corresponding Python value inside the ctypes wrapper.
            rvref ([bool]): determines if the corresponding return-by-pointer arguments need to be wrapped into :func:`ctypes.byref` (most common case),
                or passed as is (e.g., for manually prepared buffers).
            rvnames ([str]): names of returned values inside the returned named tuple. By default, return standard un-named tuple.
            tuple_single_retval (bool): determines if a single return values gets turned into a single-element tuple.
            errcheck: error-checking function which is automatically called for the return value; no function by default.
        """
        argtypes=getdefault(argtypes,self.argtypes)
        argnames=getdefault(argnames,self.argnames)
        argnames=getdefault(argnames,self._default_names("arg",len(argtypes)))
        iargs,irvals=self._split_args(argnames)
        restype=getdefault(restype,self.restype)
        return_res=getdefault(return_res,self.return_res)
        rvprep=getdefault(rvprep,self.rvprep)
        rvconv=getdefault(rvconv,self.rvconv)
        rvref=getdefault(rvref,self.rvref)
        rvref=getdefault(rvref,[True]*len(irvals))
        rvnames=getdefault(rvnames,self.rvnames)
        tuple_single_retval=getdefault(tuple_single_retval,self.tuple_single_retval)
        errcheck=getdefault(errcheck,self.errcheck)
        if return_res=="auto":
            return_res=not irvals
        sign_argtypes=list(argtypes)
        for i,ref in zip(irvals,rvref):
            if ref:
                sign_argtypes[i]=ctypes.POINTER(sign_argtypes[i])
        sign=functions.FunctionSignature([argnames[i] for i in iargs],name=func.__name__)
        setup_func(func,sign_argtypes,restype=restype,errcheck=errcheck)
        def wrapped_func(*args):
            rvals=self._prep_rval([argtypes[i] for i in irvals],rvprep,args)
            argrvals=[ctypes.byref(rv) if ref else rv for (ref,rv) in zip(rvref,rvals)]
            func_args=self._join_args(iargs,args,irvals,argrvals)
            res=func(*func_args)
            rvals=self._conv_rval(rvals,rvconv,args)
            res=self._wrap_rvals(res,rvals,rvnames,return_res)
            if (not tuple_single_retval) and len(res)==0:
                return None
            elif (not tuple_single_retval) and len(res)==1:
                return res[0]
            return res
        return sign.wrap_function(wrapped_func)
    __call__=wrap


def strprep(l):
    def prep(*args, **kwargs):
        return ctypes.create_string_buffer(l)
    return prep

def buffprep(size_arg_pos, dtype):
    el_size=data_format.DataFormat.from_desc(dtype).size
    def prep(*args, **kwargs):
        n=args[size_arg_pos]
        return ctypes.create_string_buffer(n*el_size)
    return prep
def buffconv(size_arg_pos, dtype):
    dformat=data_format.DataFormat.from_desc(dtype)
    def conv(buff, *args, **kwargs):
        n=args[size_arg_pos]
        data=ctypes.string_at(buff,n*dformat.size)
        return np.fromstring(data,dtype=dformat.to_desc("numpy"))
    return conv

class CTypesEnum(object):
    def __init__(self):
        object.__init__(self)


def struct2tuple(struct, name, prep=None, conv=None):
    fields=[f[0] for f in struct._fields_]
    tuple_cls=collections.namedtuple(name,fields)
    prep=prep or {}
    conv=conv or {}
    class CTypesStructTuple(tuple_cls):
        @classmethod
        def fromstruct(cls, obj):
            values=[getattr(obj,f) for f in fields]
            values=[(conv[f](v) if f in conv else _get_value(v)) for (f,v) in zip(fields,values)]
            return cls(*values)
        def tostruct(self):
            values=[getattr(self,f) for f in fields]
            values=[(prep[f](v,self) if f in prep else _get_value(v)) for (f,v) in zip(fields,values)]
            kwargs=dict(zip(fields,values))
            return struct(**kwargs)
    CTypesStructTuple.__name__=name
    return CTypesStructTuple