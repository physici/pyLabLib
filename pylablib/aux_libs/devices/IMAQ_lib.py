from ...core.utils import functions

import ctypes
import platform


try:

    if platform.system()=="Windows":
        lib=ctypes.windll.imaq
    else:
        raise OSError


    IMAQError=ctypes.c_uint32

    class IMAQGenericError(RuntimeError):
        """Generic IMAQdx error."""
        pass
    class IMAQLibError(IMAQGenericError):
        def __init__(self, func, code):
            self.func=func
            self.code=code
            self.msg="function '{}' raised error {}".format(func,code-0x100000000)
            RuntimeError.__init__(self,self.msg)
    def errcheck(passing=None):
        if passing is None:
            passing={0}
        def checker(result, func, arguments):
            if result not in passing:
                # print(IMAQdxLibError(func.__name__,result).msg)
                raise IMAQLibError(func.__name__,result)
            return result
        return checker

    def struct_to_tuple(value, type_type):
        args=[getattr(value,f) for f in type_type._fields]
        return type_type(*args)

    def setup_func(func, argtypes, passing=None):
        func.argtypes=argtypes
        func.restype=IMAQError
        func.errcheck=errcheck(passing=passing)

    def ctf_simple(func, argtypes, argnames, passing=None):
        sign=functions.FunctionSignature(argnames,name=func.__name__)
        setup_func(func,argtypes,passing=passing)
        def wrapped_func(*args):
            func(*args)
        return sign.wrap_function(wrapped_func)

    def _get_value(rval):
        try:
            return rval.value
        except AttributeError:
            return rval
    def ctf_rval(func, rtype, argtypes, argnames, passing=None):
        rval_idx=argtypes.index(None)
        argtypes=list(argtypes)
        argtypes[rval_idx]=ctypes.POINTER(rtype)
        sign=functions.FunctionSignature(argnames,name=func.__name__)
        setup_func(func,argtypes,passing=passing)
        def wrapped_func(*args):
            rval=rtype()
            nargs=args[:rval_idx]+(ctypes.byref(rval),)+args[rval_idx:]
            func(*nargs)
            return _get_value(rval)
        return sign.wrap_function(wrapped_func)
    def ctf_rval_str(func, maxlen, argtypes, argnames, passing=None):
        rval_idx=argtypes.index(None)
        argtypes=list(argtypes)
        argtypes[rval_idx]=ctypes.c_char_p
        sign=functions.FunctionSignature(argnames,name=func.__name__)
        setup_func(func,argtypes,passing=passing)
        def wrapped_func(*args):
            rval=ctypes.create_string_buffer(maxlen)
            nargs=args[:rval_idx]+(rval,)+args[rval_idx:]
            func(*nargs)
            return rval.value
        return sign.wrap_function(wrapped_func)









    IMAQ_MAX_API_STRING_LENGTH=256
    IMAQAPIString=ctypes.c_char*IMAQ_MAX_API_STRING_LENGTH
    def to_API_string(value):
        return ctypes.create_string_buffer(value,IMAQ_MAX_API_STRING_LENGTH)

    IMAQInterfaceID=ctypes.c_uint32
    IMAQSessionID=ctypes.c_uint32

    imgInterfaceQueryNames=ctf_rval_str(lib.imgInterfaceQueryNames, IMAQ_MAX_API_STRING_LENGTH, [ctypes.c_uint32,None], ["idx"])



except (ImportError, OSError):
    pass