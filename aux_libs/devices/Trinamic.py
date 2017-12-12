from ...core.utils import strpack
from ...core.devio import backend, data_format

from builtins import bytes
import collections
import time

_depends_local=["...core.devio.backend"]

class TrinamicError(RuntimeError):
    """Generic Trinamic error."""

i4_conv=data_format.DataFormat.from_desc(">i4")
class TMCM1100(backend.IBackendWrapper):
    """
    Trinamic stepper motor controller.
    """
    def __init__(self, conn, timeout=3.):
        conn=backend.SerialDeviceBackend.combine_serial_conn(conn,(None,9600))
        instr=backend.SerialDeviceBackend(conn,term_write="",term_read="",timeout=timeout)
        backend.IBackendWrapper.__init__(self,instr)
    
    @staticmethod
    def _build_command(comm, comm_type, value, bank=0, addr=0):
        val_str=i4_conv.convert_to_str(value)
        data_str=bytes(strpack.pack_uint(addr,1)+strpack.pack_uint(comm,1)+strpack.pack_uint(comm_type,1)+strpack.pack_uint(bank,1)+val_str)
        chksum=sum([b for b in data_str])%0x100
        return data_str+strpack.pack_uint(chksum,1)
    ReplyData=collections.namedtuple("ReplyData",["comm","status","value","addr","module"])
    @staticmethod
    def _parse_reply(reply, result_format="u4"):
        reply=bytes(reply)
        data_str=reply[:8]
        chksum=sum([b for b in data_str])%0x100
        if chksum!=reply[8]:
            raise TrinamicError("Communication error: incorrect checksum")
        addr=strpack.unpack_uint(reply[0:1])
        module=strpack.unpack_uint(reply[1:2])
        status=strpack.unpack_uint(reply[2:3])
        comm=strpack.unpack_uint(reply[3:4])
        value=data_format.DataFormat.from_desc(">"+result_format).convert_from_str(reply[4:8])[-1]
        return TMCM1100.ReplyData(comm,status,value,addr,module)
    _status_codes={100:"Success", 101:"Command loaded", 1:"Wrong checksum", 2:"Invalid command", 3:"Wrong type", 4:"Invalid value", 5:"EEPROM locked", 6:"Command not available"}
    @classmethod
    def _check_status(cls, status):
        if status not in cls._status_codes:
            raise TrinamicError("unrecognized status: {}".format(status))
        if status<100:
            raise TrinamicError("error status: {} ({})".format(status,cls._status_codes[status]))
    def query(self, comm, comm_type, value, result_format="i4", bank=0, addr=0):
        command=self._build_command(comm,comm_type,value,bank=bank,addr=addr)
        self.instr.write(command)
        reply_str=self.instr.read(9)
        reply=self._parse_reply(reply_str,result_format=result_format)
        self._check_status(reply.status)
        return reply

    def get_axis_parameter(self, parameter, result_format="i4", bank=0, addr=0):
        return self.query(6,parameter,0,result_format=result_format,bank=bank,addr=addr).value
    def set_axis_parameter(self, parameter, value, bank=0, addr=0):
        return self.query(5,parameter,value,bank=bank,addr=addr)
    def get_global_parameter(self, parameter, result_format="i4", bank=0, addr=0):
        return self.query(10,parameter,0,result_format=result_format,bank=bank,addr=addr).value
    def set_global_parameter(self, parameter, value, bank=0, addr=0):
        return self.query(9,parameter,value,bank=bank,addr=addr)

    def move(self, position, relative=False, bank=0, addr=0):
        return self.query(4,1 if relative else 0,position)
    def get_position(self, bank=0, addr=0):
        return self.get_axis_parameter(1)
    def jog(self, direction, speed):
        if not direction: # 0 or False also mean left
            direction="-"
        if direction in [1, True]:
            direction="+"
        if direction not in ["+","-"]:
            raise TrinamicError("unrecognized direction: {}".format(direction))
        return self.query(1 if direction=="+" else 2,0,speed)
    def stop(self):
        return self.query(3,0,0)

    def get_move_speed(self, bank=0, addr=0):
        return self.get_axis_parameter(4)
    def set_move_speed(self, speed, bank=0, addr=0):
        return self.set_axis_parameter(speed)

    def get_current_speed(self, bank=0, addr=0):
        return self.get_axis_parameter(3)
    def wait_move(self, bank=0, addr=0):
        while self.get_current_speed():
            time.sleep(0.05)