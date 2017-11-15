from ...core.devio import SCPI  #@UnresolvedImport

_depends_local=["...core.devio.SCPI"]


class LM500(SCPI.SCPIDevice):
    """
    Cryomagnetics LM500 level monitor.
    """
    def __init__(self, addr):
        SCPI.SCPIDevice.__init__(self,(addr,9600),backend="serial")
        self.instr.term_read="\n"
        self._add_settings_node("interval",self.get_interval,self.set_interval)
    
    def _instr_write(self, msg):
        return self.instr.write(msg,read_echo=True)
    def _instr_read(self, raw=False):
        return self.instr.readline(remove_term=True).strip()
    
    @staticmethod
    def _str_to_sec(s):
        s=s.strip().split(":")
        s=[int(n.strip()) for n in s]
        return s[0]*60**2+s[1]*60+s[2]
    @staticmethod
    def _sec_to_str(s):
        return "{:02d}:{:02d}:{:02d}".format(int(s/60.**2),int((s/60.)%60.),int(s%60.))
    def get_interval(self):
        return self._str_to_sec(self.ask("INTVL?"))
    def set_interval(self, intvl):
        if not isinstance(intvl,basestring):
            intvl=self._sec_to_str(intvl)
        self.write("INTVL",intvl)
        return self.get_interval()
    
    def get_level(self, channel=1):
        res=self.ask("MEAS? {}".format(channel))
        return float(res.split()[0])