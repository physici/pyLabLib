from ...core.devio import backend,units  #@UnresolvedImport
import collections

_depends_local=["...core.devio.backend"]

class OphirDevice(backend.IBackendWrapper):
    """
    Generic Ophir device.
    """
    def __init__(self, port_addr, timeout=3.):
        instr=backend.SerialDeviceBackend((port_addr,9600),timeout=timeout,term_read="\r\n",term_write="\r\n")
        backend.IBackendWrapper.__init__(self,instr)
    
    def _parse_response(self, comm, resp):
        resp=resp.strip()
        if resp.startswith("?"):
            raise RuntimeError("Command {} returned error: {}".format(comm,resp[1:].strip()))
        if resp.startswith("*"):
            return resp[1:].strip()
        raise RuntimeError("Command {} returned unrecognized response: {}".format(comm,resp))
    def query(self, comm, timeout=None):
        comm=comm.strip()
        with self.instr.single_op():
            self.instr.flush_read()
            self.instr.write(comm)
            resp=self.instr.readline(timeout=timeout)
        return self._parse_response(comm,resp)


class VegaPowerMeter(OphirDevice):
    """
    Ophir Vega power meter.
    """
    def get_power(self):
        power=self.query("$SP")
        if power.lower()=="over":
            return "over"
        return float(power)

    WavelengthInfo=collections.namedtuple("WavelengthInfo",["mode","rng","curr_idx","presets","curr_wavelength"])
    def get_wavelength_info(self):
        info=[i.strip() for i in self.query("$AW").split() if i.strip()]
        mode=info[0]
        rng=(float(info[1])*1E-9,float(info[2])*1E-9)
        curr_idx=int(info[3])
        presets=[float(w)*1E-9 for w in info[4:]]
        return self.WavelengthInfo(mode,rng,curr_idx-1,presets,presets[curr_idx-1])
    def get_wavelength(self):
        return self.get_wavelength_info().curr_wavelength
    def set_wavelength(self, wavelength):
        self.query("$WL{:d}".format(int(wavelength*1E9)))
        return self.get_wavelength()

    RangeInfo=collections.namedtuple("RangeInfo",["curr_idx","ranges","curr_range"])
    def get_range_info(self):
        info=[i.strip() for i in self.query("$AR").split() if i.strip()]
        curr_idx=int(info[0])
        ranges=[units.convert_power_units(float(r[:-2]),r[-2:],"W") for r in info[3:]]
        if curr_idx<0:
            curr_range=info[3+curr_idx]
        else:
            curr_range=ranges[curr_idx]
        return self.RangeInfo(curr_idx,ranges,curr_range)
    def get_range(self):
        return self.get_range_info().curr_range
    def get_range_idx(self):
        return self.get_range_info().curr_idx
    def set_range_idx(self, rng_idx):
        self.query("$WN{:d}".format(rng_idx))
        return self.get_range_idx()

    def is_filter_in(self):
        return int(self.query("$FQ").split()[0].strip())==2
    def set_filter(self, filter_in):
        self.query("$FQ{:d}".format(2 if filter_in else 1))
        return self.is_filter_in()