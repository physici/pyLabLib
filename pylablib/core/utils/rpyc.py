"""Routines and classes related to RPyC package"""

from . import module as module_utils, net, py3, strpack

import numpy as np
import rpyc

import importlib
import pickle



_numpy_block_size=int(2**20)


def _obtain_single(proxy, conn):
    if conn and isinstance(conn.root,SocketTunnelService):
        rem_root=conn.root
        loc_root=conn.root.getconn().root
        async_send=rpyc.async_(rem_root.tunnel_send)
        async_send(proxy)
        return loc_root.tunnel_recv()
    else:
        return rpyc.classic.obtain(proxy)

def obtain(proxy, conn=None):
    """
    Obtain a remote netfref object by value (i.e., copy it to the local Python instance).

    Wrapper around :func:`rpyc.classic.obtain` with some special cases handling.
    """
    if not isinstance(proxy,rpyc.BaseNetref):
        return proxy
    if isinstance(proxy, np.ndarray):
        elsize=np.prod(proxy.shape,dtype="u8")
        bytesize=proxy.dtype.itemsize*elsize
        if bytesize>_numpy_block_size:
            fproxy=proxy.flatten()
            loc=np.zeros(elsize,dtype=proxy.dtype.str)
            block_size=_numpy_block_size//proxy.dtype.itemsize
            for pos in range(0,elsize,block_size):
                loc[pos:pos+block_size]=_obtain_single(fproxy[pos:pos+block_size],conn=conn)
            return loc.reshape(proxy.shape)
        else:
            return _obtain_single(fproxy,conn=conn)
    return rpyc.classic.obtain(proxy)



_tunnel_block_size=int(2**20)
class SocketTunnelService(rpyc.SlaveService):
    def __init__(self, server=False):
        rpyc.SlaveService.__init__(self)
        self.server=server
    _default_tunnel_timeout=10.
    def send_socket(self):
        def listen(s):
            s.set_timeout(self._default_tunnel_timeout)
            self.tunnel_socket=s
        remote_call=rpyc.async_(self._conn.root.recv_socket)
        def port_func(port):
            remote_call(net.get_local_addr(),port)
        net.listen(None,0,listen,port_func=port_func,timeout=self._default_tunnel_timeout,connections_number=1)
    def recv_socket(self, dst_addr, dst_port):
        self.tunnel_socket=net.ClientSocket(timeout=self._default_tunnel_timeout)
        self.tunnel_socket.connect(dst_addr,dst_port)
    def tunnel_send(self, obj, pickled=True):
        if pickled:
            obj=pickle.dumps(obj)
        nchunks=max((len(obj)-1)//_tunnel_block_size+1,1)
        self.tunnel_socket.send_fixedlen(strpack.pack_uint(nchunks,4,">"))
        for pos in range(0,len(obj),_tunnel_block_size):
            self.tunnel_socket.send_decllen(obj[pos:pos+_tunnel_block_size])
    def tunnel_recv(self, pickled=True):
        nchunks=strpack.unpack_uint(self.tunnel_socket.recv_fixedlen(4))
        obj=b""
        for _ in range(nchunks):
            obj+=self.tunnel_socket.recv_decllen()
        return pickle.loads(obj) if pickled else obj
    def on_connect(self, conn):
        rpyc.SlaveService.on_connect(self,conn)
        if not self.server:
            self.send_socket()
class DeviceService(rpyc.SlaveService):
    """
    Device RPyC service.

    Expands on :class:`rpyc.SlaveService` by adding :meth:`get_device` method,
    which tracks opened devices and closes them automatically on disconnect.
    """
    def on_connect(self, conn):
        rpyc.SlaveService.on_connect(self,conn)
        self.devices=[]
    def on_disconnect(self, conn):
        for dev in self.devices:
            try:
                dev.close()
            except:
                pass
        self.devices=[]
        rpyc.SlaveService.on_disconnect(self,conn)
    def get_device(self, module, cls, *args, **kwargs):
        """
        Connect to a device.

        `cls` and `module` are names of the device class and the containing module
        (for module name the ``"pylablib.aux_libs.devices"`` prefix can be omitted)
        """
        try:
            module=importlib.import_module(module)
        except ModuleNotFoundError:
            module=importlib.import_module(module_utils.get_library_name()+".aux_libs.devices."+module)
        module._rpyc=True
        cls=module.__dict__[cls]
        dev=cls(*args,**kwargs)
        self.devices.append(dev)
        return dev

def run_device_service(port=18812):
    """Start :class:`DeviceService` at the given port"""
    rpyc.ThreadedServer(DeviceService,port=port).start()