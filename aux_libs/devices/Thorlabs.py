from ...core.devio import SCPI, units, backend  #@UnresolvedImport

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
        conn=backend.SerialDeviceBackend.combine_serial_conn(conn,("COM1",115200))
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