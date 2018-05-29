from ...core.devio import SCPI, units, backend  #@UnresolvedImport
from ...core.utils import strpack

import re
try:
    import ft232
except (ImportError,NameError,OSError):
    pass

import collections

_depends_local=["...core.devio.SCPI"]


class PM100D(SCPI.SCPIDevice):
    """
    Thorlabs PM100D optical Power Meter.

    Args:
        addr: connection address (usually, a VISA connection string)
    """
    def __init__(self, addr):
        SCPI.SCPIDevice.__init__(self,addr)
    
    def setup_power_measurement(self):
        """Switch the device into power measurement mode"""
        self.write(":CONFIGURE:SCALAR:POWER")
        
    def get_power(self):
        """Get the power readings"""
        self.write(":MEASURE:POWER")
        value,unit=self.ask(":read?","value")
        return units.convert_power_units(value,unit or "W","W",case_sensitive=False)


class ThorlabsInterface(SCPI.SCPIDevice):
    """
    Generic Thorlabs device interface using Serial communication.

    Args:
        conn: serial connection parameters (usually port or a tuple containing port and baudrate)
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

    Args:
        conn: serial connection parameters (usually port or a tuple containing port and baudrate)
        respect_bound(bool): if ``True``, avoid crossing the boundary between the first and the last position in the wheel
    """
    def __init__(self, conn, respect_bound=True):
        ThorlabsInterface.__init__(self,conn)
        self._add_settings_node("pos",self.get_position,self.set_position)
        self._add_settings_node("pcount",self.get_pcount,self.set_pcount)
        self._add_settings_node("speed",self.get_speed,self.set_speed)
        self.pcount=self.get_pcount()
        self.respect_bound=respect_bound

    def get_position(self):
        """Get the wheel position (starting from 1)"""
        self.flush()
        return self.ask("pos?","int")
    def set_position(self, pos):
        """Set the wheel position (starting from 1)"""
        if self.respect_bound: # check if the wheel could go through zero; if so, manually go around instead
            cur_pos=self.get_position()
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
        return self.get_position()

    def get_pcount(self):
        """Get the number of wheel positions (6 or 12)"""
        self.flush()
        return self.ask("pcount?","int")
    def set_pcount(self, pcount):
        self.write("pcount={}".format(pcount))
        self.pcount=self.get_pcpount()
        return self.pcount

    def get_speed(self):
        """Get the motion speed"""
        self.flush()
        return self.ask("speed?","int")
    def set_speed(self, speed):
        """Set the motion speed"""
        self.write("speed={}".format(speed))
        return self.get_speed()




class MDT69xA(ThorlabsInterface):
    """
    Thorlabs MDT693/4A high-voltage source.

    Uses MDT693A program interface, so should be compatible with both A and B versions.

    Args:
        conn: serial connection parameters (usually port or a tuple containing port and baudrate)
    """
    def __init__(self, conn):
        ThorlabsInterface.__init__(self,conn)

    _id_comm="I"
    def get_voltage(self, channel="x"):
        """Get the output voltage in Volts at a given channel"""
        self.flush()
        if not channel.lower() in "xyz":
            raise ValueError("unrecognized channel name: {}".format(channel))
        resp=self.ask(channel.upper()+"R?")
        resp=resp.strip()[2:-1].strip()
        return float(resp)
    def set_voltage(self, voltage, channel="x"):
        """Set the output voltage in Volts at a given channel"""
        if not channel.lower() in "xyz":
            raise ValueError("unrecognized channel name: {}".format(channel))
        self.write(channel.upper()+"V{:.3f}".format(voltage))
        return self.get_voltage(channel=channel)

    def get_voltage_range(self):
        """Get the selected voltage range in Volts (75, 100 or 150)."""
        resp=self.ask("%")
        resp=resp.strip()[2:-1].strip()
        return float(resp)






class KinesisDevice(backend.IBackendWrapper):
    """
    Generic Kinesis device.

    Implements FTDI chip connectivity via pyft232 (virtual serial interface).

    Args:
        conn: serial connection parameters (usually 8-digit device serial number).
    """
    def __init__(self, conn, timeout=3.):
        conn=backend.FT232DeviceBackend.combine_conn(conn,(None,115200))
        instr=backend.FT232DeviceBackend(conn,term_write=b"",term_read=b"",timeout=timeout)
        backend.IBackendWrapper.__init__(self,instr)

    @staticmethod
    def list_devices(filter_ids=True):
        """
        List all connected devices.

        Return list of tuples ``(conn, description)``.
        If ``filter_ids==True``, only leave devices with Tholabs-like IDs (8-digit numbers).
        Otherwise, show all devices (some of them might not be Thorlabs-related).
        """
        def _is_thorlabs_id(id):
            return re.match(b"^\d{8}$",id[0]) is not None
        ids=ft232.list_devices()
        if filter_ids:
            ids=[id for id in ids if _is_thorlabs_id(id)]
        return ids
    def send_comm_nodata(self, messageID, param1=0x00, param2=0x00, source=0x01, dest=0x50):
        """
        Send a message with no associated data.

        For details, see APT communications protocol.
        """
        msg=strpack.pack_uint(messageID,2,"<")+strpack.pack_uint(param1,1)+strpack.pack_uint(param2,1)+strpack.pack_uint(dest,1)+strpack.pack_uint(source,1)
        self.instr.write(msg)
    def send_comm_data(self, messageID, data, source=0x01, dest=0x50):
        """
        Send a message with associated data.

        For details, see APT communications protocol.
        """
        msg=strpack.pack_uint(messageID,2,"<")+strpack.pack_uint(len(data),2)+strpack.pack_uint(dest,1)+strpack.pack_uint(source,1)
        self.instr.write(msg+data)

    CommNoData=collections.namedtuple("CommNoData",["messageID","param1","param2","source","dest"])
    def recv_comm_nodata(self):
        """
        Receive a message with no associated data.

        For details, see APT communications protocol.
        """
        msg=self.instr.read(6)
        messageID=strpack.unpack_uint(msg[0:2],"<")
        param1=strpack.unpack_uint(msg[2:3])
        param2=strpack.unpack_uint(msg[3:4])
        source=strpack.unpack_uint(msg[4:5])
        dest=strpack.unpack_uint(msg[5:6])
        return self.CommNoData(messageID,param1,param2,source,dest)
    CommData=collections.namedtuple("CommData",["messageID","data","source","dest"])
    def recv_comm_data(self):
        """
        Receive a message with associated data.

        For details, see APT communications protocol.
        """
        msg=self.instr.read(6)
        messageID=strpack.unpack_uint(msg[0:2],"<")
        datalen=strpack.unpack_uint(msg[2:4],"<")
        source=strpack.unpack_uint(msg[4:5])
        dest=strpack.unpack_uint(msg[5:6])
        data=self.instr.read(datalen)
        return self.CommData(messageID,data,source,dest)

    DeviceInfo=collections.namedtuple("DeviceInfo",["serial_no","model_no","fw_ver","hw_type","hw_ver","mod_state","nchannels"])
    def get_info(self, dest=0x50):
        """
        Get device info.
        """
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
        """Identify the physical device (by, e.g., blinking status LED or screen)"""
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
        """Set the flip mount position (either 0 or 1)"""
        self.send_comm_nodata(0x046A,channel,2 if pos else 1)
    def get_position(self, channel=0):
        """
        Get the flip mount position (either 0 or 1).

        Return ``None`` if the mount is current moving.
        """
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