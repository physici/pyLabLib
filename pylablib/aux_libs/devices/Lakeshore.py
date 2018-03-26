from ...core.devio import backend, SCPI #@UnresolvedImport
from ...core.utils import funcargparse  #@UnresolvedImport

_depends_local=["...core.devio.SCPI"]


class Lakeshore218(SCPI.SCPIDevice):
    """
    Lakeshore 218 temperature controller.
    """
    def __init__(self, conn, timeout=1.):
        conn=backend.SerialDeviceBackend.combine_serial_conn(conn,("COM1",9600,7,'E',1))
        SCPI.SCPIDevice.__init__(self,conn,backend="serial",timeout=timeout,term_write="\r\n",term_read="\r\n")
    
    def is_enabled(self, channel):
        return self.ask("INPUT? {}".format(channel+1),"bool")
    def set_enabled(self, channel, enabled=True):
        self.write("INPUT {} {}".format(channel+1, 1 if enabled else 0))
        return self.is_enabled(channel)
        
    def get_sensor_type(self, group):
        return self.ask("INTYPE? {}".format(group),"int")
    def set_sensor_type(self, group, type):
        self.write("INTYPE {} {}".format(group, type))
        return self.get_sensor_type(group)
    
    def read_channel(self, channel):
        return self.ask("KRDG? {}".format(channel+1),"float")
    def read_all_channels(self):
        data=self.ask("KRDG? 0")
        return [float(x.strip()) for x in data.strip().split(",")]


class Lakeshore370(SCPI.SCPIDevice):
    """
    Lakeshore 370 temperature controller.
    """
    def __init__(self, addr):
        SCPI.SCPIDevice.__init__(self,addr)
    
    def get_resistance(self, channel):
        return self.ask("RDGR? {:2d}".format(channel),"float")
    def get_sensor_power(self, channel):
        return self.ask("RDGPWR? {:2d}".format(channel),"float")
    
    def select_meas_channel(self, channel):
        self.write("SCAN {:2d},0".format(channel))
    def get_meas_channel(self):
        return int(self.ask("SCAN?").split(",")[0].strip())
    def setup_meas_channel(self, channel=None, mode="V", exc_range=1, res_range=22, autorange=True):
        funcargparse.check_parameter_range(mode,"mode","IV")
        channel=0 if channel is None else channel
        mode=0 if mode=="V" else 1
        autorange=1 if autorange else 0
        self.write("RDGRNG {:2d},{},{:2d},{:2d},{},0".format(channel,mode,exc_range,res_range,autorange))
    
    def setup_heater_openloop(self, heater_range, heater_percent, heater_res=100.):
        self.write("CMODE 3")
        self.write("CSET 1,0,1,25,1,{},{:f}".format(heater_range,heater_res))
        self.write("HTRRNG {}".format(heater_range))
        self.write("MOUT {:f}".format(heater_percent))
    def get_heater_settings_openloop(self):
        cset_reply=[s.strip() for s in self.ask("CSET?").split(",")]
        heater_percent=self.ask("MOUT?","float")
        heater_range=self.ask("HTRRNG?","int")
        #return int(cset_reply[5]),heater_percent,float(cset_reply[6])
        return heater_range,heater_percent,float(cset_reply[6])
    
    def set_analog_output(self, channel, value):
        if value==0:
            self.write("ANALOG {},0,0,1,1,500.,0,0.".format(channel))
        else:
            self.write("ANALOG {},0,2,1,1,500.,0,{:f}".format(channel,value))
        return self.get_analog_output(channel)
    def get_analog_output(self, channel):
        return self.ask("AOUT? {}".format(channel),"float")