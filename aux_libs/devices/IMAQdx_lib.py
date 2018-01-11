from ...core.utils import functions, py3

import numpy as np
import ctypes
import collections




lib=ctypes.windll.niimaqdx


IMAQdxError=ctypes.c_uint32

class IMAQdxLibError(RuntimeError):
    def __init__(self, func, code):
        self.func=func
        self.code=code
        try:
            self.desc=IMAQdxGetErrorString(code)
        except IMAQdxLibError:
            self.desc="Unknown"
        self.msg="function '{}' raised error {}({})".format(func,code-0x100000000,self.desc)
        RuntimeError.__init__(self,self.msg)
def errcheck(passing=None):
    if passing is None:
        passing={0}
    def checker(result, func, arguments):
        if result not in passing:
            # print(IMAQdxLibError(func.__name__,result).msg)
            raise IMAQdxLibError(func.__name__,result)
        return result
    return checker

def struct_to_tuple(value, type_type):
    args=[getattr(value,f) for f in type_type._fields]
    return type_type(*args)

def setup_func(func, argtypes, passing=None):
    func.argtypes=argtypes
    func.restype=IMAQdxError
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
    argtypes[rval_idx:rval_idx+1]=[ctypes.c_char_p,ctypes.c_uint32]
    sign=functions.FunctionSignature(argnames,name=func.__name__)
    setup_func(func,argtypes,passing=passing)
    def wrapped_func(*args):
        rval=ctypes.create_string_buffer(maxlen)
        nargs=args[:rval_idx]+(rval,maxlen)+args[rval_idx:]
        func(*nargs)
        return rval.value
    return sign.wrap_function(wrapped_func)
def ctf_buff(func, argtypes, argnames, build_buff=None, conv_buff=None, passing=None):
    buff_idx=argtypes.index(None)
    argtypes=list(argtypes)
    argtypes[buff_idx]=ctypes.c_char_p
    sign=functions.FunctionSignature(argnames,name=func.__name__)
    setup_func(func,argtypes,passing=passing)
    def wrapped_func(*args):
        buff=build_buff(*args)
        nargs=args[:buff_idx]+(buff,)+args[buff_idx:]
        func(*nargs)
        return conv_buff(buff,*args)
    return sign.wrap_function(wrapped_func)









IMAQDX_MAX_API_STRING_LENGTH=512
IMAQdxAPIString=ctypes.c_char*IMAQDX_MAX_API_STRING_LENGTH
def to_API_string(value):
    return ctypes.create_string_buffer(value,IMAQDX_MAX_API_STRING_LENGTH)

IMAQdxSession=ctypes.c_uint32

IMAQdxCameraControlMode=ctypes.c_uint32
IMAQdxCameraControlMode_enum={"controller":0,"listener":1}
IMAQdxBusType=ctypes.c_uint32
class IMAQdxCameraInformation(ctypes.Structure):
    _fields_=[  ("Type",ctypes.c_uint32),
                ("Version",ctypes.c_uint32),
                ("Flags",ctypes.c_uint32),
                ("SerialNumberHi",ctypes.c_uint32),
                ("SerialNumberLo",ctypes.c_uint32),
                ("BusType",IMAQdxBusType),
                ("InterfaceName",IMAQdxAPIString),
                ("VendorName",IMAQdxAPIString),
                ("ModelName",IMAQdxAPIString),
                ("CameraFileName",IMAQdxAPIString),
                ("CameraAttributeURL",IMAQdxAPIString)]
IMAQdxCameraInformation_p=ctypes.POINTER(IMAQdxCameraInformation)
TMAQdxCameraInformation=collections.namedtuple("TMAQdxCameraInformation",
    ["Type","Version","Flags","SerialNumberHi","SerialNumberLo","BusType","InterfaceName","VendorName","ModelName","CameraFileName","CameraAttributeURL"])

IMAQdxAttributeType=ctypes.c_uint32
IMAQdxAttributeType_enum={0:"u32", 1:"i64", 2:"f64", 3:"str", 4:"enum", 5:"bool", 6:"command", 7:"blob", 0xFFFFFFFF:"guard"}
class IMAQdxAttributeInformation(ctypes.Structure):
    _fields_=[  ("Type",IMAQdxAttributeType),
                ("Readable",ctypes.c_uint32),
                ("Writable",ctypes.c_uint32),
                ("Name",IMAQdxAPIString)]
TMAQdxAttributeInformation=collections.namedtuple("TMAQdxAttributeInformation",["Name","Type","Readable","Writable"])
IMAQdxAttributeInformation_p=ctypes.POINTER(IMAQdxAttributeInformation)
IMAQdxAttributeVisibility=ctypes.c_uint32
IMAQdxAttributeVisibility_enum={"simple":0x1000,"intermediate":0x2000,"advanced":0x4000}
IMAQdxValueType=ctypes.c_uint32
IMAQdxValueType_enum={0:"u32", 1:"i64", 2:"f64", 3:"str", 4:"enum", 5:"bool", 6:"str_disp", 0xFFFFFFFF:"guard"}
class IMAQdxEnumItem(ctypes.Structure):
    _fields_=[  ("Value",ctypes.c_uint32),
                ("Reserved",ctypes.c_uint32),
                ("Name",IMAQdxAPIString)]
IMAQdxEnumItem_p=ctypes.POINTER(IMAQdxEnumItem)
TIMAQdxEnumItem=collections.namedtuple("TIMAQdxEnumItem",["Value","Name"])

IMAQdxBufferNumberMode=ctypes.c_uint32




IMAQdxGetErrorString=ctf_rval_str(lib.IMAQdxGetErrorString, IMAQDX_MAX_API_STRING_LENGTH, [IMAQdxError,None], ["code"])


setup_func(lib.IMAQdxEnumerateCameras,[IMAQdxCameraInformation_p,ctypes.POINTER(ctypes.c_uint32),ctypes.c_uint32])
def IMAQdxEnumerateCameras(connected):
    cnt=ctypes.c_uint32()
    lib.IMAQdxEnumerateCameras(ctypes.cast(0,IMAQdxCameraInformation_p),ctypes.byref(cnt),connected)
    cams=(IMAQdxCameraInformation*cnt.value)()
    lib.IMAQdxEnumerateCameras(cams,ctypes.byref(cnt),connected)
    return [struct_to_tuple(c,TMAQdxCameraInformation) for c in cams]
IMAQdxOpenCamera=ctf_rval(lib.IMAQdxOpenCamera, IMAQdxSession, [ctypes.c_char_p,IMAQdxCameraControlMode,None], ["name","mode"])
IMAQdxCloseCamera=ctf_simple(lib.IMAQdxCloseCamera, [IMAQdxSession], ["sid"])


def _new_attr_value(attr_type):
    if attr_type==0:
        return ctypes.c_uint32()
    if attr_type==1:
        return ctypes.c_int64()
    if attr_type==2:
        return ctypes.c_double()
    if attr_type==3:
        return IMAQdxAPIString()
    if attr_type==4:
        return IMAQdxEnumItem()
    if attr_type==5:
        return ctypes.c_bool()
    raise ValueError("unknown attribute type: {}".format(attr_type))
def _to_attr_value(value, value_type=None):
    if value_type is None:
        if isinstance(value,int) or isinstance(value,np.long) or isinstance(value,np.integer):
            value_type=1
        elif isinstance(value,float) or isinstance(value,np.floating):
            value_type=2
        elif isinstance(value,py3.textstring):
            value_type=3
        else:
            raise ValueError("can't automatically determine value type for {}".format(value))
    if value_type==0:
        val=ctypes.c_uint32(value)
    elif value_type==1:
        val=ctypes.c_int64(value)
    elif value_type==2:
        val=ctypes.c_double(value)
    elif value_type==3:
        val=to_API_string(value)
    elif value_type==4:
        val=IMAQdxEnumItem(Value=value)
    elif value_type==5:
        val=ctypes.c_bool(value)
    else:
        raise ValueError("unknown attribute type: {}".format(value_type))
    return val,value_type
def _from_attr_value(value, attr_type):
    if attr_type in [0,1,2,3,5]:
        return value.value
    if attr_type==4:
        return TIMAQdxEnumItem(value.Value,value.Name)
    raise ValueError("unknown attribute type: {}".format(attr_type))
setup_func(lib.IMAQdxEnumerateAttributes2,[IMAQdxSession,IMAQdxAttributeInformation_p,ctypes.POINTER(ctypes.c_uint32),ctypes.c_char_p,IMAQdxAttributeVisibility])
def IMAQdxEnumerateAttributes2(sid, root, visibility):
    cnt=ctypes.c_uint32()
    lib.IMAQdxEnumerateAttributes2(sid,ctypes.cast(0,IMAQdxAttributeInformation_p),ctypes.byref(cnt),root,visibility)
    attrs=(IMAQdxAttributeInformation*cnt.value)()
    lib.IMAQdxEnumerateAttributes2(sid,attrs,ctypes.byref(cnt),root,visibility)
    return [TMAQdxAttributeInformation(a.Name,a.Type,a.Readable,a.Writable) for a in attrs]
setup_func(lib.IMAQdxGetAttribute,[IMAQdxSession,ctypes.c_char_p,IMAQdxAttributeType,ctypes.c_voidp])
def IMAQdxGetAttribute(sid, name, attr_type):
    val=_new_attr_value(attr_type)
    lib.IMAQdxGetAttribute(sid,name,attr_type,ctypes.byref(val))
    return _from_attr_value(val,attr_type)
lib.IMAQdxSetAttribute.restype=IMAQdxError
lib.IMAQdxSetAttribute.errcheck=errcheck()
def IMAQdxSetAttribute(sid, name, value, value_type):
    val,value_type=_to_attr_value(value,value_type)
    lib.IMAQdxSetAttribute(sid,name,ctypes.c_uint32(value_type),val)
IMAQdxGetAttributeType=ctf_rval(lib.IMAQdxGetAttributeType, IMAQdxAttributeType, [IMAQdxSession,ctypes.c_char_p,None], ["sid","name"])
setup_func(lib.IMAQdxGetAttributeMinimum,[IMAQdxSession,ctypes.c_char_p,IMAQdxAttributeType,ctypes.c_voidp])
def IMAQdxGetAttributeMinimum(sid, name, attr_type):
    val=_new_attr_value(attr_type)
    lib.IMAQdxGetAttributeMinimum(sid,name,attr_type,ctypes.byref(val))
    return _from_attr_value(val,attr_type)
setup_func(lib.IMAQdxGetAttributeMaximum,[IMAQdxSession,ctypes.c_char_p,IMAQdxAttributeType,ctypes.c_voidp])
def IMAQdxGetAttributeMaximum(sid, name, attr_type):
    val=_new_attr_value(attr_type)
    lib.IMAQdxGetAttributeMaximum(sid,name,attr_type,ctypes.byref(val))
    return _from_attr_value(val,attr_type)
setup_func(lib.IMAQdxGetAttributeIncrement,[IMAQdxSession,ctypes.c_char_p,IMAQdxAttributeType,ctypes.c_voidp])
def IMAQdxGetAttributeIncrement(sid, name, attr_type):
    val=_new_attr_value(attr_type)
    lib.IMAQdxGetAttributeIncrement(sid,name,attr_type,ctypes.byref(val))
    return _from_attr_value(val,attr_type)
IMAQdxIsAttributeReadable=ctf_rval(lib.IMAQdxIsAttributeReadable, ctypes.c_bool, [IMAQdxSession,ctypes.c_char_p,None], ["sid","name"])
IMAQdxIsAttributeWritable=ctf_rval(lib.IMAQdxIsAttributeWritable, ctypes.c_bool, [IMAQdxSession,ctypes.c_char_p,None], ["sid","name"])
IMAQdxGetAttributeTooltip=ctf_rval_str(lib.IMAQdxGetAttributeTooltip, IMAQDX_MAX_API_STRING_LENGTH, [IMAQdxSession,ctypes.c_char_p,None], ["sid","name"])
IMAQdxGetAttributeUnits=ctf_rval_str(lib.IMAQdxGetAttributeUnits, IMAQDX_MAX_API_STRING_LENGTH, [IMAQdxSession,ctypes.c_char_p,None], ["sid","name"])
IMAQdxGetAttributeDescription=ctf_rval_str(lib.IMAQdxGetAttributeDescription, IMAQDX_MAX_API_STRING_LENGTH, [IMAQdxSession,ctypes.c_char_p,None], ["sid","name"])
IMAQdxGetAttributeDisplayName=ctf_rval_str(lib.IMAQdxGetAttributeDisplayName, IMAQDX_MAX_API_STRING_LENGTH, [IMAQdxSession,ctypes.c_char_p,None], ["sid","name"])
setup_func(lib.IMAQdxEnumerateAttributeValues,[IMAQdxSession,ctypes.c_char_p,IMAQdxEnumItem_p,ctypes.POINTER(ctypes.c_uint32)])
def IMAQdxEnumerateAttributeValues(sid, name):
    cnt=ctypes.c_uint32()
    lib.IMAQdxEnumerateAttributeValues(sid,name,ctypes.cast(0,IMAQdxEnumItem_p),ctypes.byref(cnt))
    values=(IMAQdxEnumItem*cnt.value)()
    lib.IMAQdxEnumerateAttributeValues(sid,name,values,ctypes.byref(cnt))
    return [_from_attr_value(v,4) for v in values]


IMAQdxConfigureAcquisition=ctf_simple(lib.IMAQdxConfigureAcquisition, [IMAQdxSession,ctypes.c_uint32,ctypes.c_uint32], ["sid","continuous","buffer_count"])
IMAQdxConfigureGrab=ctf_simple(lib.IMAQdxConfigureGrab, [IMAQdxSession], ["sid"])
IMAQdxStartAcquisition=ctf_simple(lib.IMAQdxStartAcquisition, [IMAQdxSession], ["sid"])
IMAQdxStopAcquisition=ctf_simple(lib.IMAQdxStopAcquisition, [IMAQdxSession], ["sid"])
IMAQdxUnconfigureAcquisition=ctf_simple(lib.IMAQdxUnconfigureAcquisition, [IMAQdxSession], ["sid"])


setup_func(lib.IMAQdxGetImageData,[IMAQdxSession,ctypes.c_voidp,ctypes.c_uint32,IMAQdxBufferNumberMode,ctypes.c_uint32,ctypes.POINTER(ctypes.c_uint32)])
def IMAQdxGetImageData(sid, size, mode, buffer_num):
    buff=ctypes.create_string_buffer(size)
    actual_buffer_num=ctypes.c_uint32()
    lib.IMAQdxGetImageData(sid,buff,size,mode,buffer_num,ctypes.byref(actual_buffer_num))
    return ctypes.string_at(buff,size),actual_buffer_num