from ...core.utils import py3, general, funcargparse
from ...core.devio import data_format

import numpy as np
import numpy.random

import time, collections, os.path


def gen_uid():
    uid_arr=numpy.random.randint(0,256,size=8,dtype="u1")
    return py3.as_bytes(uid_arr)

current_version=0x01
valid_magic=b"eCM"
valid_versions=[0x01]

def read_int(f, dtype):
    return int(np.fromfile(f,dtype,count=1)[0])
def read_float(f, dtype):
    return float(np.fromfile(f,dtype,count=1)[0])

class ECamFrame(object):
    def __init__(self, data, uid="new", timestamp="new"):
        object.__init__(self)
        self.data=data
        self.uid=gen_uid() if uid=="new" else uid
        self.timestamp=time.time() if timestamp=="new" else timestamp
    
    def update_timestamp(self, timestamp=None):
        self.timestamp=timestamp or time.time()

    def uid_to_int(self):
        return read_int("<f8",self.uid) if self.uid else None
    def uid_to_hex(self):
        return "".join(["{:02x}".format(d) for d in self.uid]) if self.uid else None


class ECamFormatError(IOError):
    pass


THeader=collections.namedtuple("THeader",["header_size","image_bytes","shape","dtype","stype","version","uid","timestamp"])
stypes={0x00:"none",0x01:"raw"}
stypes_inv=general.invert_dict(stypes)
dtypes={0x00:"<i1",0x01:"<i2",0x02:"<i4",0x03:"<i8",0x10:"<u1",0x11:"<u2",0x12:"<u4",0x13:"<u8",
        0x20:">i1",0x21:">i2",0x22:">i4",0x23:">i8",0x30:">u1",0x31:">u2",0x32:">u4",0x33:">u8",
        0x80:">f4",0x81:">f8",0xa0:"<f4",0xa1:"<f8"}
dtypes_inv=general.invert_dict(dtypes)

class ECamFormatter(object):
    def __init__(self, stype="raw", dtype=None, shape=(None,None), save_magic=True):
        object.__init__(self)
        self.save_magic=save_magic
        self.stype=stype
        self.dtype=dtype
        self.shape=shape
    
    def _build_frame(self, header, data):
        return ECamFrame(data,header.uid,header.timestamp)
    def _read_header(self, f, full=True):
        try:
            header_size=read_int(f,"<u4")
        except IndexError:
            raise StopIteration
        if header_size<12 or (header_size<44 and header_size not in {12,24,26,28,32,40}):
            raise ECamFormatError("bad file format: header size is {}".format(header_size))
        image_bytes=read_int(f,"<u8")
        if header_size>12:
            shape=tuple([read_int(f,"<u4") for _ in range(3)])
        else:
            shape=self.shape
        if shape[2]==0:
            shape=shape[:2]
        if (None not in self.shape) and shape!=self.shape:
            raise ValueError("data shape {} doesn't agree with the formatter shape {}".format(shape,self.shape))
        dtype=read_int(f,"<u2") if header_size>24 else self.dtype
        stype=read_int(f,"<u2") if header_size>26 else self.stype
        if header_size>28:
            version=read_int(f,"u1")
            if version not in valid_versions:
                raise ECamFormatError("bad file format: unsupported version 0x{:02x}".format(version))
            magic=f.read(3)
            if magic!=valid_magic:
                raise ECamFormatError("bad file format: invalid magic {}".format(magic))
        else:
            version=None
        uid=f.read(8) if header_size>32 else None
        timestamp=read_float(f,"<f8") if header_size>40 else None
        if header_size>48:
            f.seek(header_size-48,1)
        return THeader(header_size,image_bytes,shape,dtype,stype,version,uid,timestamp)
    def skip_frame(self, f):
        header=self._read_header(f,full=False)
        f.seek(header.image_bytes,1)
        return header.header_size,header.image_bytes
    def read_frame(self, f, return_format="frame"):
        funcargparse.check_parameter_range(return_format,"return_format",{"frame","image","raw"})
        header=self._read_header(f)
        if (None in header.shape) or header.stype is None or header.dtype is None:
            raise ECamFormatError("bad file format: not enough header data to read image")
        if header.stype not in stypes:
            raise ECamFormatError("bad file format: unknown storage type 0x{:04x}".format(header.stype))
        if header.dtype not in dtypes:
            raise ECamFormatError("bad file format: unknown data type 0x{:04x}".format(header.stype))
        if header.stype==stypes_inv["raw"]:
            df=data_format.DataFormat.from_desc(dtypes[header.dtype])
            nelem=int(np.prod(header.shape,dtype="u8"))
            if df.size*nelem!=header.image_bytes:
                shape_str="x".join([str(s) for s in header.shape])
                raise ECamFormatError("bad file format: mismatched frame byte size: expect {}x{}={}, got {}".format(
                    shape_str,df.size,nelem*df.size,header.image_bytes))
            img=np.fromfile(f,dtype=df.to_desc(),count=nelem)
            if len(img)!=nelem:
                raise ECamFormatError("bad file format: expected {} elements, found {}".format(nelem,len(img)))
            img=img.reshape(header.shape)
        if return_format=="frame":
            return self._build_frame(header,img)
        elif return_format=="image":
            return img
        else:
            return header,img


    def _format_frame(self, frame):
        if isinstance(frame,ECamFrame):
            data=np.asarray(frame.data)
            uid=frame.uid
            timestamp=frame.timestamp
        else:
            data=np.asarray(frame)
            uid,timestamp=None,None
        if self.dtype is not None:
            data=data.astype(self.dtype)
        if (None not in self.shape) and data.shape!=self.shape:
            raise ValueError("data shape {} doesn't agree with the formatter shape {}".format(data.shape,self.shape))
        hsize=48
        if timestamp is None:
            hsize=40
        if uid is None:
            hsize=32
            if not self.save_magic:
                hsize=28
        if data.ndim not in [2,3]:
            raise ValueError("can only save 2D and 3D arrays")
        df=data_format.DataFormat.from_desc(str(data.dtype))
        dsize=int(np.prod(data.shape,dtype="u8"))*df.size
        header=THeader(hsize,dsize,data.shape,dtypes_inv[str(df.to_desc())],stypes_inv["raw"],current_version,uid,timestamp)
        return header,data
    def _write_header(self, header, f):
        np.asarray(header.header_size).astype("<u4").tofile(f)
        np.asarray(header.image_bytes).astype("<u8").tofile(f)
        if None not in header.shape:
            shape=header.shape+(0,)*(3-len(header.shape))
            np.asarray(shape,dtype="u4").astype("<u4").tofile(f)
        else:
            return
        if header.dtype is not None:
            np.asarray(header.dtype).astype("<u2").tofile(f)
        else:
            return
        if header.stype is not None:
            np.asarray(header.stype).astype("<u2").tofile(f)
        else:
            return
        if header.header_size>28:
            np.asarray(header.version).astype("u1").tofile(f)
            f.write(valid_magic)
        else:
            return
        if header.uid is not None:
            f.write(header.uid)
        else:
            return
        if header.timestamp is not None:
            np.asarray(header.timestamp).astype("<f8").tofile(f)
        else:
            return
    def write_frame(self, frame, f):
        header,data=self._format_frame(frame)
        self._write_header(header,f)
        if (None in header.shape) or header.stype is None or header.dtype is None:
            raise ECamFormatError("bad header format: not enough header data to write image")
        if header.stype not in stypes:
            raise ECamFormatError("bad header format: unknown storage type 0x{:04x}".format(header.stype))
        if header.dtype not in dtypes:
            raise ECamFormatError("bad header format: unknown data type 0x{:04x}".format(header.stype))
        if header.stype==stypes_inv["raw"]:
            data.astype(dtype=dtypes[header.dtype]).tofile(f)
        return header.header_size,header.image_bytes


def save_ecam(frames, path, append=True, formatter=None):
    """
    Save `frames` into a .ecam datafile.

    If ``append==False``, clear the file before writing the frames.
    `formatter` specifies :class:`ECamFormatter` instance for frame saving.
    """
    mode="ab" if append else "wb"
    formatter=formatter or ECamFormatter()
    with open(path,mode) as f:
        for fr in frames:
            formatter.write_frame(fr,f)



class ECamReader(object):
    """
    Reader class for .ecam files.

    Allows transparent access to frames by reading them from the file on the fly (without loading the whole file).
    Supports determining length, indexing (only positive single-element indices) and iteration.

    Args:
        path(str): path to .ecam file.
        same_size(bool): if ``True``, assume that all frames have the same size (including header), which speeds up random access and obtaining number of frames;
            otherwise, the first time the length is determined or a large-index frame is accessed can take a long time (all subsequent calls are faster).
        return_format(str): format for return data. Can be ``"frame"`` (return :class:`ECamFrame` object with all metadata),
            ``"image"`` (return only image array), or ``"raw"`` (return tuple ``(header, image)`` with raw data).
        formatter(ECamFormatter): formatter for saving
    """
    def __init__(self, path, same_size=False, return_format="frame", formatter=None):
        object.__init__(self)
        self.path=path
        self.frame_offsets=[0]
        self.frames_num=None
        self.same_size=same_size
        self.return_format=return_format
        self.formatter=formatter or ECamFormatter()

    def _read_frame_at(self, offset):
        with open(self.path,"rb") as f:
            f.seek(offset)
            return self.formatter.read_frame(f,return_format=self.return_format)
    def _read_next_frame(self, f, skip=False):
        if skip:
            self.formatter.skip_frame(f)
            data=None
        else:
            data=self.formatter.read_frame(f,return_format=self.return_format)
        self.frame_offsets.append(f.tell())
        return data
    def _read_frame(self, idx):
        idx=int(idx)
        if self.same_size:
            if len(self.frame_offsets)==1:
                with open(self.path,"rb") as f:
                    self._read_next_frame(f,skip=True)
            offset=self.frame_offsets[1]*idx
            return self._read_frame_at(offset)
        else:
            if idx<len(self.frame_offsets):
                return self._read_frame_at(self.frame_offsets[idx])
            next_idx=len(self.frame_offsets)-1
            offset=self.frame_offsets[-1]
            with open(self.path,"rb") as f:
                f.seek(offset)
                while next_idx<=idx:
                    data=self._read_next_frame(f,next_idx<idx)
                    next_idx+=1
            return data

    def _fill_offsets(self):
        if self.frames_num is not None:
            return
        if self.same_size:
            file_size=os.path.getsize(self.path)
            if file_size==0:
                self.frames_num=0
            else:
                with open(self.path,"rb") as f:
                    self._read_next_frame(f,skip=True)
                if file_size%self.frame_offsets[1]:
                    raise IOError("File size {} is not a multile of single frame size {}".format(file_size,self.frame_offsets[1]))
                self.frames_num=file_size//self.frame_offsets[1]
        else:
            offset=self.frame_offsets[-1]
            try:
                with open(self.path,"rb") as f:
                    f.seek(offset)
                    while True:
                        self._read_next_frame(f,skip=True)
            except StopIteration:
                pass
            self.frames_num=len(self.frame_offsets)-1
    
    def size(self):
        """Get the total number of frames"""
        self._fill_offsets()
        return self.frames_num
    __len__=size

    def __getitem__(self, idx):
        try:
            return self._read_frame(idx)
        except StopIteration:
            raise IndexError("index {} is out of range".format(idx))
    def get_data(self, idx):
        """Get a single frame at the given index (only non-negative indices are supported)"""
        return self[idx]
    def __iter__(self):
        return self.iterrange()
    def iterrange(self, *args):
        """
        iterrange([start,] stop[, step])

        Iterate over frames starting with `start` ending at `stop` (``None`` means until the end of file) with the given `step`.
        """
        start,stop,step=0,None,1
        if len(args)==1:
            stop,=args
        elif len(args)==2:
            start,stop=args
        elif len(args)==3:
            start,stop,step=args
        try:
            n=start
            while True:
                yield self._read_frame(n)
                n+=step
                if stop is not None and n>=stop:
                    break
        except StopIteration:
            pass
    def read_all(self):
        """Read all available frames"""
        return list(self.iterrange())