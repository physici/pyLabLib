from ...core.devio import SCPI, units, backend  #@UnresolvedImport
from ...core.utils import strpack

import collections

_depends_local=["...core.devio.SCPI"]


class PM100D(SCPI.SCPIDevice):
    """
    Thorlabs PM100D optical Power Meter.
    """
    def __init__(self, addr):
        SCPI.SCPIDevice.__init__(self,addr)
    
    def setup_power_measurement(self):
        self.write(":CONFIGURE:SCALAR:POWER")
        
    def get_power(self):
        self.write(":MEASURE:POWER")
        value,unit=self.ask(":read?","value")
        return units.convert_power_units(value,unit or "W","W",case_sensitive=False)


class ThorlabsInterface(SCPI.SCPIDevice):
    """
    Generic Thorlabs device interface.
    """
    def __init__(self, conn):
        conn=backend.SerialDeviceBackend.combine_conn(conn,("COM1",115200))
        SCPI.SCPIDevice.__init__(self,conn,backend="serial",term_read=["\r","\n"],term_write="\r")
    
    def _instr_write(self, msg):
        return self.instr.write(msg,read_echo=True)
    def _instr_read(self, raw=False):
        data=""
        while not data:
            data=self.instr.readline(remove_term=True).strip()
            if data[:1]==b">":
                data=data[1:].strip()
        return data


class FW(ThorlabsInterface):
    """
    Thorlabs FW102/202 motorized filter wheels.
    """
    def __init__(self, conn, respect_bound=True):
        ThorlabsInterface.__init__(self,conn)
        self._add_settings_node("pos",self.get_pos,self.set_pos)
        self._add_settings_node("pcount",self.get_pcount,self.set_pcount)
        self._add_settings_node("speed",self.get_speed,self.set_speed)
        self.pcount=self.get_pcount()
        self.respect_bound=respect_bound

    def get_pos(self):
        self.flush()
        return self.ask("pos?","int")
    def set_pos(self, pos):
        if self.respect_bound: # check if the wheel could go through zero; if so, manually go around instead
            cur_pos=self.get_pos()
            if abs(pos-cur_pos)>=self.pcount//2: # could switch by going through zero
                medp1=(2*cur_pos+pos)//3
                medp2=(cur_pos+2*pos)//3
                self.write("pos={}".format(medp1))
                self.write("pos={}".format(medp2))
                self.write("pos={}".format(pos))
            else:
                self.write("pos={}".format(pos))
        else:
            self.write("pos={}".format(pos))
        return self.get_pos()

    def get_pcount(self):
        self.flush()
        return self.ask("pcount?","int")
    def set_pcount(self, pcount):
        self.write("pcount={}".format(pcount))
        self.pcount=self.get_pcpount()
        return self.pcount

    def get_speed(self):
        self.flush()
        return self.ask("speed?","int")
    def set_speed(self, speed):
        self.write("speed={}".format(speed))
        return self.get_speed()




class MDT69xA(ThorlabsInterface):
    """
    Thorlabs MDT693/4A high-voltage source.

    Uses MDT693A program interface, so should be compatible with both A and B versions.
    """
    def __init__(self, conn):
        ThorlabsInterface.__init__(self,conn)

    _id_comm="I"
    def get_voltage(self, channel="x"):
        self.flush()
        if not channel.lower() in "xyz":
            raise ValueError("unrecognized channel name: {}".format(channel))
        resp=self.ask(channel.upper()+"R?")
        resp=resp.strip()[2:-1].strip()
        return float(resp)
    def set_voltage(self, voltage, channel="x"):
        if not channel.lower() in "xyz":
            raise ValueError("unrecognized channel name: {}".format(channel))
        self.write(channel.upper()+"V{:.3f}".format(voltage))
        return self.get_voltage(channel=channel)

    def get_voltage_range(self):
        resp=self.ask("%")
        resp=resp.strip()[2:-1].strip()
        return float(resp)






class KinesisDevice(backend.IBackendWrapper):
    """
    Generic Kinesis device.

    Implements FTDI chip connectivity via pyft232 (virtual serial interface).
    """
    def __init__(self, conn, timeout=3.):
        conn=backend.FT232DeviceBackend.combine_conn(conn,(None,115200))
        instr=backend.FT232DeviceBackend(conn,term_write=b"",term_read=b"",timeout=timeout)
        backend.IBackendWrapper.__init__(self,instr)

    def send_comm_nodata(self, messageID, param1=0x00, param2=0x00, source=0x01, dest=0x50):
        msg=strpack.pack_uint(messageID,2,"<")+strpack.pack_uint(param1,1)+strpack.pack_uint(param2,1)+strpack.pack_uint(source,1)+strpack.pack_uint(dest,1)
        self.instr.write(msg)
    def send_comm_data(self, messageID, data, source=0x01, dest=0x50):
        msg=strpack.pack_uint(messageID,2,"<")+strpack.pack_uint(len(data),2)+strpack.pack_uint(source,1)+strpack.pack_uint(dest,1)
        self.instr.write(msg+data)

    CommNoData=collections.namedtuple("CommNoData",["messageID","param1","param2","source","dest"])
    def recv_comm_nodata(self):
        msg=self.instr.read(6)
        messageID=strpack.unpack_uint(msg[0:2],"<")
        param1=strpack.unpack_uint(msg[2:3])
        param2=strpack.unpack_uint(msg[3:4])
        source=strpack.unpack_uint(msg[4:5])
        dest=strpack.unpack_uint(msg[5:6])
        return self.CommNoData(messageID,param1,param2,source,dest)
    CommData=collections.namedtuple("CommData",["messageID","data","source","dest"])
    def recv_comm_data(self):
        msg=self.instr.read(6)
        messageID=strpack.unpack_uint(msg[0:2],"<")
        datalen=strpack.unpack_uint(msg[2:4],"<")
        source=strpack.unpack_uint(msg[4:5])
        dest=strpack.unpack_uint(msg[5:6])
        data=self.instr.read(datalen)
        return self.CommData(messageID,data,source,dest)

    DeviceInfo=collections.namedtuple("DeviceInfo",["serial_no","model_no","fw_ver","hw_type","hw_ver","mod_state","nchannels"])
    def get_info(self, dest=0x50):
        self.send_comm_nodata(0x0005,dest=dest)
        data=self.recv_comm_data().data
        serial_no=strpack.unpack_uint(data[:4],"<")
        model_no=data[4:12].decode()
        while model_no[-1]==b"\x00":
            model_no=model_no[:-1]
        fw_ver="{}.{}.{}".format(strpack.unpack_uint(data[16:17]),strpack.unpack_uint(data[15:16]),strpack.unpack_uint(data[14:15]))
        hw_type=strpack.unpack_uint(data[12:14],"<")
        hw_ver=strpack.unpack_uint(data[78:80],"<")
        mod_state=strpack.unpack_uint(data[80:82],"<")
        nchannels=strpack.unpack_uint(data[82:84],"<")
        return self.DeviceInfo(serial_no,model_no,fw_ver,hw_type,hw_ver,mod_state,nchannels)

    def blink(self, dest=0x50):
        self.send_comm_nodata(0x0223,dest=dest)


class MFF(KinesisDevice):
    """
    MFF (Motorized Filter Flip Mount) device.

    Implements FTDI chip connectivity via pyft232 (virtual serial interface).
    """
    def __init__(self, conn):
        KinesisDevice.__init__(self,conn)
        self._add_settings_node("position",self.get_position,self.set_position)
    def set_position(self, pos, channel=0):
        self.send_comm_nodata(0x046A,channel,2 if pos else 1)
    def get_position(self, channel=0):
        self.send_comm_nodata(0x0429)
        data=self.recv_comm_data().data
        status=strpack.unpack_uint(data[2:6],"<")
        if status&0x01: # low limit
            return 0
        if status&0x02: # high limit
            return 1
        if status&0x2F0: # moving
            return None
        raise RuntimeError("error getting MF10x position: status {:08x}".format(status))