from ...core.devio import backend  #@UnresolvedImport


class PfeifferError(RuntimeError):
    """
    Pfiffer devices reading error.
    """
    pass

class TPG261(backend.IBackendWrapper):
    """
    TPG 261 series pressure gauge.
    """
    def __init__(self, conn, timeout=3.):
        conn=backend.SerialDeviceBackend.combine_serial_conn(conn,("COM1",9600))
        instr=backend.SerialDeviceBackend(conn,timeout=timeout,term_write="",term_read="\r\n")
        backend.IBackendWrapper.__init__(self,instr)
    
    def comm(self, msg):
        self.instr.write(msg+"\r\n")
        rsp=self.instr.readline()
        if len(rsp)==1:
            if rsp[:1]==b"\x15":
                raise PfeifferError("device returned negative acknowledgement")
            elif rsp[:1]==b"\x06":
                return
        raise PfeifferError("device returned unexpected acknowledgement: {}".format(rsp))
    def query(self, msg):
        self.comm(msg)
        self.instr.write("\05")
        return self.instr.readline()
        
    _pstats=["OK","underrange","overrange","sensor error","sensor off","no sensor","ID error"]
    def get_pressure(self, channel=1):
        resp=self.query("PR{}".format(channel))
        stat,press=[s.strip() for s in resp.split(",")]
        stat=int(stat)
        if stat:
            raise PfeifferError("pressure reading error: status {} ({})".format(stat,self._pstats[stat]))
        return float(press)