from ...core.utils.py3 import textstring
from ...core.devio import SCPI  #@UnresolvedImport

_depends_local=["...core.devio.SCPI"]


class LM500(SCPI.SCPIDevice):
    """
    Cryomagnetics LM500 level monitor.
    """
    def __init__(self, addr):
        SCPI.SCPIDevice.__init__(self,(addr,9600),backend="serial")
        self.instr.term_read="\n"
        self.instr.term_write="\n"
        self._add_settings_node("interval",self.get_interval,self.set_interval)
    
    def _instr_write(self, msg):
        return self.instr.write(msg,read_echo=True,read_echo_delay=0.1)
    def _instr_read(self, raw=False):
        data=""
        while not data:
            data=self.instr.readline(remove_term=True).strip()
        return data

    def get_channel(self):
        return self.ask("CHAN?","int")
    def set_channel(self, channel=1):
        self.write("CHAN",channel)
        return self.get_channel()

    def get_type(self, channel=1):
        chan_type=self.ask("TYPE? {}".format(channel),"int")
        return ["LHe","LN"][chan_type]
    def _check_channel_LHe(self, op, channel=None):
        if channel is None:
            channel=self.get_channel()
        if self.get_type(channel)=="LN":
            raise RuntimeError("LN channel doesn't support {}".format(op))
    
    def get_mode(self):
        self._check_channel_LHe("measurement modes")
        return self.ask("MODE?").upper()
    def set_mode(self, mode):
        self._check_channel_LHe("measurement modes")
        self.write("MODE",mode)
        return self.get_mode()

    @staticmethod
    def _str_to_sec(s):
        s=s.strip().split(":")
        s=[int(n.strip()) for n in s]
        return s[0]*60**2+s[1]*60+s[2]
    @staticmethod
    def _sec_to_str(s):
        return "{:02d}:{:02d}:{:02d}".format(int(s/60.**2),int((s/60.)%60.),int(s%60.))
    def get_interval(self):
        self._check_channel_LHe("measurement intervals")
        return self._str_to_sec(self.ask("INTVL?"))
    def set_interval(self, intvl):
        self._check_channel_LHe("measurement intervals")
        if not isinstance(intvl,textstring):
            intvl=self._sec_to_str(intvl)
        self.write("INTVL",intvl)
        return self.get_interval()
    
    def start_meas(self, channel=1):
        self.write("MEAS",channel)
    def _get_stb(self):
        return self.ask("*STB?","int")
    def wait_meas(self, channel=1):
        mask=0x01 if channel==1 else 0x04
        while not self._get_stb()&mask:
            self.sleep(0.1)
    def get_level(self, channel=1):
        res=self.ask("MEAS? {}".format(channel))
        return float(res.split()[0])
    def measure_level(self, channel=1):
        self.start_meas(channel=channel)
        self.wait_meas(channel=channel)
        return self.get_level(channel=channel)

    def start_fill(self, channel=1):
        self.write("FILL",channel)
    def get_fill_status(self, channel=1):
        res=self.ask("FILL? {}".format(channel)).lower()
        if res in {"off","timeout"}:
            return res
        spres=res.split()
        if len(spres)==1 or spres[1] in ["m","min"]:
            return float(spres[0])*60.
        if spres[1] in ["s","sec"]:
            return float(spres[0])
        raise ValueError("unxepected response: {}".format(res))