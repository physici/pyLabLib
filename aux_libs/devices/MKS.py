from ...core.devio import backend  #@UnresolvedImport


class MKS9xx(backend.IBackendWrapper):
    """
    MKS 9xx series pressure gauge.
    """
    def __init__(self, port_addr, dev_addr=254, timeout=10.):
        instr=backend.SerialDeviceBackend((port_addr,115200),timeout=timeout,term_write="",term_read="")
        backend.IBackendWrapper.__init__(self,instr)
        self.dev_addr=dev_addr
    
    def query(self, reg):
        query="@{:03d}{}?;FF".format(self.dev_addr,reg)
        self.instr.write(query)
        resp=self.instr.read_multichar_term(";FF")
        if resp[4:].startswith("NAK"):
            raise self.instr.Error("device replied with error '{}' to query '{}'".format(resp,query))
        elif resp[4:].startswith("ACK"):
            return resp[7:]
        else:
            raise self.instr.Error("unrecognized response '{}' to query '{}'".format(resp,query)) 
    def comm(self, reg, value):
        query="@{:03d}{}!{};FF".format(self.dev_addr,reg,value)
        self.instr.write(query)
        
    def get_pressure(self, chan=3):
        resp=self.query("PR{}".format(chan))
        return float(resp)