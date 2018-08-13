
from ..utils import general, py3
import numpy as np
import pickle



##### Complex structures file IO #####

default_byteorder="<"
_sbase=0x01
_tbase=0x10
_bobase=0x20

fdtypes={0x40:">f2",0x41:">f4",0x42:">f8",0x60:"<f2",0x61:"<f4",0x62:"<f8"}
fdtypes_inv=general.invert_dict(fdtypes)
idtypes={0x00:"<i1",0x01:"<i2",0x02:"<i4",0x03:"<i8",0x10:"<u1",0x11:"<u2",0x12:"<u4",0x13:"<u8",
        0x20:">i1",0x21:">i2",0x22:">i4",0x23:">i8",0x30:">u1",0x31:">u2",0x32:">u4",0x33:">u8"}
idtypes_inv=general.invert_dict(idtypes)
sdtypes={0x80:"sp<u1",0x81:"sp<u2",0x82:"sp<u4",0x83:"sp<u8",
         0xa0:"sp>u1",0xa1:"sp>u2",0xa2:"sp>u4",0xa3:"sp>u8"}
sdtypes_inv=general.invert_dict(sdtypes)
pkdtypes={}
for pkp in [0,1,2,3]:
    for bo in [0,1]:
        for s in [1,2,4,8]:
            pkdtypes[0x100+0x40*pkp+0x20*bo+s]="pk{}{}u{}".format(pkp,"<>"[bo],s)
pkdtypes_inv=general.invert_dict(pkdtypes)
asdtypes={0x1000:"as<u1",0x1001:"as<u2",0x1020:"as>u1",0x1021:"as>u2"}
asdtypes_inv=general.invert_dict(asdtypes)

alltypes=general.merge_dicts(fdtypes,idtypes,sdtypes,pkdtypes)
alltypes_inv=general.invert_dict(alltypes)

def write_num(x, f, dtype):
    if dtype[0] not in "<>":
        dtype=default_byteorder+dtype
    if dtype in idtypes_inv:
        np.asarray(int(x)).astype(dtype).tofile(f)
    elif dtype in fdtypes_inv:
        np.asarray(float(x)).astype(dtype).tofile(f)
    else:
        raise ValueError("unrecognzied dtype: {}".format(dtype))
def write_str(s, f, dtype, strict=False):
    s=py3.as_bytes(s)
    if dtype=="s":
        f.write(s)
    elif dtype.startswith("sp"):
        write_num(len(s),f,dtype[2:])
        f.write(s)
    elif dtype.startswith("s"):
        if strict and len(s)!=int(dtype[1:]):
            raise ValueError("string length {} doesn't agree with dtype {}".format(len(s),int(dtype[1:])))
        f.write(s)
    else:
        raise ValueError("unrecognzied dtype: {}".format(dtype))
def write_pickle(v, f, dtype):
    if dtype.startswith("pk"):
        proto=int(dtype[2])
        sdtype=dtype[3:]
        v=pickle.dumps(v,protocol=proto)
        write_str(v,f,"sp"+sdtype)
    else:
        raise ValueError("unrecognzied dtype: {}".format(dtype))
def write_val(v, f, dtype):
    if isinstance(dtype,py3.textstring):
        if dtype.startswith("s"):
            write_str(v,f,dtype)
        elif dtype.startswith("pk"):
            write_pickle(v,f,dtype)
        else:
            write_num(v,f,dtype)
    if isinstance(dtype,tuple):
        if len(v)!=len(dtype):
            raise ValueError("value {} doesn't agree with dtype {}".format(v,dtype))
        for (el,dt) in zip(v,dtype):
            write_val(el,f,dt)

def read_num(f, dtype):
    if dtype[0] not in "<>":
        dtype=default_byteorder+dtype
    if dtype in idtypes_inv:
        return int(np.fromfile(f,dtype=dtype,count=1)[0])
    elif dtype in fdtypes_inv:
        return float(np.fromfile(f,dtype=dtype,count=1)[0])
    else:
        raise ValueError("unrecognzied dtype: {}".format(dtype))
def read_str(f, dtype):
    if dtype.startswith("sp"):
        sl=read_num(f,dtype[2:])
        return py3.as_str(f.read(sl))
    elif dtype.startswith("s"):
        sl=int(dtype[1:])
        return py3.as_str(f.read(sl))
    else:
        raise ValueError("unrecognzied dtype: {}".format(dtype))
def read_pickle(f, dtype):
    if dtype.startswith("pk"):
        sdtype=dtype[3:]
        v=read_str(f,"sp"+sdtype)
        return pickle.loads(v)
    else:
        raise ValueError("unrecognzied dtype: {}".format(dtype))
def read_val(f, dtype):
    if isinstance(dtype,py3.textstring):
        if dtype.startswith("s"):
            return read_str(f,dtype)
        elif dtype.startswith("pk"):
            return read_pickle(f,dtype)
        else:
            return read_num(f,dtype)
    if isinstance(dtype,tuple):
        return tuple([ read_val(f,dt) for dt in dtype ])