"""Routines and classes related to RPyC package"""

from . import module as module_utils, net, py3, strpack

import numpy as np
import rpyc

import importlib
import pickle
import warnings


_default_packers={"numpy":np.ndarray.tostring,"pickle":pickle.dumps}
_default_unpackers={"pickle":pickle.loads}
def _is_tunnel_service(serv):
    return hasattr(serv,"tunnel_socket")
def _obtain_single(proxy, serv):
    if serv and _is_tunnel_service(serv):
        loc_serv=serv.peer
        async_send=rpyc.async_(serv.tunnel_send)
        async_send(proxy,packer="pickle")
        return loc_serv.tunnel_recv(unpacker="pickle")
    else:
        return rpyc.classic.obtain(proxy)


_numpy_block_size=int(2**20)
def obtain(proxy, serv=None):
    """
    Obtain a remote netfref object by value (i.e., copy it to the local Python instance).

    Wrapper around :func:`rpyc.classic.obtain` with some special cases handling.
    `serv` specifies the current remote service. If it is of type :class:`SocketTunnelSurvice`, use its socket tunnel for faster transfer.
    """
    if not isinstance(proxy,rpyc.BaseNetref):
        return proxy
    if isinstance(proxy, np.ndarray):
        elsize=np.prod(proxy.shape,dtype="u8")
        bytesize=proxy.dtype.itemsize*elsize
        if serv and _is_tunnel_service(serv):
            loc_serv=serv.peer
            async_send=rpyc.async_(serv.tunnel_send)
            async_send(proxy,packer="numpy")
            data=loc_serv.tunnel_recv()
            return np.frombuffer(data,dtype=proxy.dtype.str).reshape(proxy.shape)
        else:
            if bytesize>_numpy_block_size:
                fproxy=proxy.flatten()
                loc=np.zeros(elsize,dtype=proxy.dtype.str)
                block_size=_numpy_block_size//proxy.dtype.itemsize
                for pos in range(0,elsize,block_size):
                    loc[pos:pos+block_size]=rpyc.classic.obtain(fproxy[pos:pos+block_size])
                return loc.reshape(proxy.shape)
    return _obtain_single(proxy,serv)

class SocketTunnelService(rpyc.SlaveService):
    """
    Extension of the standard :class:`rpyc.SlaveService` with built-in network socket tunnel for faster data transfer.

    In order for the tunnel to work, services on both ends need to be subclasses of :class:`SocketTunnelService`.
    Because of the initial setup protocol, the two services are asymmetric: one should be 'server' (corresponding to the listening server),
    and one should be 'client' (external connection). The roles are decided by the `server` constructor parameter.
    """
    _tunnel_block_size=int(2**20)
    def __init__(self, server=False):
        rpyc.SlaveService.__init__(self)
        self.server=server
    _default_tunnel_timeout=10.
    def _recv_socket(self):
        """Set up a listener to receive a socket connection from the other service."""
        def listen(s):
            s.set_timeout(self._default_tunnel_timeout)
            self.tunnel_socket=s
        remote_call=rpyc.async_(self._conn.root._send_socket)
        def port_func(port):
            remote_call(net.get_local_addr(),port)
        net.listen(None,0,listen,port_func=port_func,timeout=self._default_tunnel_timeout,connections_number=1)
    def _send_socket(self, dst_addr, dst_port):
        """Set up a client socket to connect to the other service."""
        self.tunnel_socket=net.ClientSocket(timeout=self._default_tunnel_timeout)
        self.tunnel_socket.connect(dst_addr,dst_port)

    def tunnel_send(self, obj, packer=None):
        """
        Send data throught the socket tunnel.

        If `packer` is not ``None``, it defines a function to convert `obj` to a bytes string.
        """
        packer=_default_packers.get(packer,packer)
        if packer:
            obj=packer(obj)
        nchunks=(len(obj)-1)//self._tunnel_block_size+1
        self.tunnel_socket.send_fixedlen(strpack.pack_uint(nchunks,4,">"))
        for pos in range(0,len(obj),self._tunnel_block_size):
            self.tunnel_socket.send_decllen(obj[pos:pos+self._tunnel_block_size])
    def tunnel_recv(self, unpacker=None):
        """
        Receive data sent throught the socket tunnel.

        If `unpacker` is not ``None``, it defines a function to convert the received bytes string into an object.
        """
        nchunks=strpack.unpack_uint(self.tunnel_socket.recv_fixedlen(4))
        chunks=[]
        for _ in range(nchunks):
            chunks.append(self.tunnel_socket.recv_decllen())
        obj=b"".join(chunks)
        unpacker=_default_unpackers.get(unpacker,unpacker)
        return unpacker(obj) if unpacker else obj
    def on_connect(self, conn):
        rpyc.SlaveService.on_connect(self,conn)
        self.peer=conn.root
        if not self.server:
            self._recv_socket()

class DeviceService(SocketTunnelService):
    """
    Device RPyC service.

    Expands on :class:`SocketTunnelService` by adding :meth:`get_device` method,
    which opens local devices, tracks them, and closes them automatically on disconnect.
    """
    def __init__(self):
        SocketTunnelService.__init__(self,server=True)
    def on_connect(self, conn):
        SocketTunnelService.on_connect(self,conn)
        self.devices=[]
    def on_disconnect(self, conn):
        for dev in self.devices:
            try:
                dev.close()
            except:
                pass
        self.devices=[]
        SocketTunnelService.on_disconnect(self,conn)
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

def connect_device_service(addr, port=18812):
    """Connect to the :class:`DeviceService` running at the given address and port"""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            return rpyc.connect(addr,port=port,service=SocketTunnelService).root
        except net.socket.timeout:
            return None