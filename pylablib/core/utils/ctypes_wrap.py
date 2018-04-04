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



class StructWrap(object):
    class _struct(ctypes.Structure):
        _fields_=[]
    _prep={}
    _conv={}
    _tup={}
    _default={}
    def __init__(self, struct=None):
        struct=struct or self._struct()
        if not isinstance(struct,self._struct):
            raise ValueError("source should be of type {}".format(self._struct.__name__))
        fnames,ftypes=zip(*self._struct._fields_)
        for f in fnames:
            if f in self._default:
                v=self._default[f]
            else:
                cv=getattr(struct,f)
                v=self._conv[f](cv) if f in self._conv else _get_value(cv)
            setattr(self,f,v)
        self.conv()
    def to_struct(self):
        params=self.prepdict()
        fnames,ftypes=zip(*self._struct._fields_)
        for f in fnames:
            if f not in params:
                params[f]=getattr(self,f)
        ordparams=[params[f] for f in fnames]
        cparams={}
        for f,t in self._struct._fields_:
            if f in self._prep:
                cv=self._prep[f](*ordparams)
            else:
                cv=t(params[f])
            cparams[f]=cv
        return self.prep(self._struct(**cparams))

    def prep(self, struct):
        return struct
    def prepdict(self):
        return {}
    def conv(self):
        pass
    def tupdict(self):
        return {}
    def tup(self):
        params=self.tupdict()
        fnames,ftypes=zip(*self._struct._fields_)
        for f in fnames:
            if f not in params:
                params[f]=getattr(self,f)
            if f in self._tup:
                params[f]=self._tup[f](params[f])
        vals=[params[f] for f in fnames]
        tcls=collections.namedtuple(self.__class__.__name__,fnames)
        return tcls(*vals)

    @classmethod
    def prep_struct(cls, *args):
        return cls().to_struct()
    @classmethod
    def tup_struct(cls, struct, *args):
        return cls(struct).tup()