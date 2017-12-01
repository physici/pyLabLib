from ...core.devio import backend  #@UnresolvedImport
from ...core.utils import general, log  #@UnresolvedImport

import time
import numpy as np

_depends_local=["...core.devio.backend"]



class NIGPIBSerialDevice(backend.IBackendWrapper):
    """
    National Instruments Serial<->GPIB converter.
    """
    def __init__(self, port_addr, timeout=10.):
        instr=backend.SerialDeviceBackend((port_addr,57600,8,'N',1,0,1),timeout=timeout,term_write="\n",term_read="\r\n")
        backend.IBackendWrapper.__init__(self,instr)
    
    def get_id(self):
        self.instr.flush_read()
        return self.instr.ask("id",delay=0.1,read_all=True)
    
    def init_GPIB(self, addr=0):
        self.instr.flush_read()
        self.instr.write("onl 1") # online
        self.instr.write("caddr {}",format(addr)) # set brdige GPIB address
        self.instr.write("sic")
        self.instr.write("eos D")
        self.instr.write("eot")
        self.instr.write("rsc 1") # set as controller
        self.instr.write("sre 0")
        self.instr.write("ist 1")
        self.instr.write("tmo 1,1") # set timeouts
        self.instr.flush_read()
        
    def get_stat(self):
        self.instr.flush_read()
        self.instr.write("stat n")
        stat=self.instr.readlines(4)
        self.instr.flush_read()
        return stat
        
    def write(self, addr, data):
        self.instr.flush_read()
        self.instr.write("wrt {}\n{}".format(addr,data))
        self.instr.flush_read()
    def read(self, addr, size=256):
        self.instr.flush_read()
        self.instr.write("rd #{} {}".format(size,addr))
        data=self.instr.read(size)
        l=int(self.instr.readline())
        self.instr.flush_read()
        return data[:l]
    
    
    

class NIGPIBSerialBackend(backend.IDeviceBackend):
    """
    Device backend for the National Instruments Serial<->GPIB converter.
    """
    _default_operation_cooldown=0.05
    _default_read_cooldown=0.5
    Error=backend.SerialDeviceBackend.Error
    _backend="NIGPIBSerial"
    
    def __init__(self, bridge_conn, dev_addr, timeout=10., term_write=None, term_read=None):
        if term_read is None:
            term_read=["\r\n"]
        backend.IDeviceBackend.__init__(self,dev_addr,term_write=term_write,term_read=term_read)
        self._operation_cooldown=self._default_operation_cooldown
        self._read_cooldown=self._default_read_cooldown
        self.timeout=timeout
        self.bridge=NIGPIBSerialDevice(bridge_conn,timeout=timeout)
        self.bridge.init_GPIB()
    
    def open(self):
        return self.bridge.open()
    def close(self):
        return self.bridge.close()
    
    def set_timeout(self, timeout):
        self.timeout=timeout
    def get_timeout(self):
        return self.timeout
    
    def cooldown(self):
        if self._operation_cooldown>0:
            time.sleep(self._operation_cooldown)
    def read_cooldown(self):
        time.sleep(self._read_cooldown)
        
    def readline(self, remove_term=True, timeout=None):
        with self.using_timeout(timeout):
            data=""
            countdown=general.Countdown(self.timeout)
            while True:
                data=data+self.bridge.read(self.conn)
                self.cooldown()
                for t in self.term_read:
                    if data.find(t)>=0:
                        return data[:data.find(t)] if remove_term else data[:data.find(t)+len(t)]
                if countdown.passed():
                    raise self.Error("readline operation timeout")
                self.read_cooldown()
            
    def read(self, size=None):
        if size is None:
            data=self.bridge.read(self.conn)
            self.cooldown()
        else:
            data=""
            countdown=general.Countdown(self.timeout)
            while len(data)<size:
                data=data+self.bridge.read(self.conn,size=size-len(data))
                self.cooldown()
                if countdown.passed():
                    raise self.Error("read operation timeout")
                self.read_cooldown()
        return data
    def flush_read(self):
        return len(self.read())
    def write(self, data, flush=True, read_echo=False):
        if self.term_write:
            data=data+self.term_write
        self.bridge.write(self.conn,data)
        self.cooldown()
        if read_echo:
            self.readline()
            self.cooldown()





try:
    import nidaqmx

    class NIUSB6009(object):
        """
        National Instruments USB-6009 I/O device.
        """
        _default_retry_delay=5.
        _default_retry_times=5
        def __init__(self, dev):
            object.__init__(self)
            self.dev=dev
            self.voltage_range=10.
            self.rate=1E4
            self._retry_delay=2.
            self._retry_times=5
            
        def close(self):
            pass
        
        def __enter__(self):
            return self
        def __exit__(self, *args, **vargs):
            return False
        
        def set_voltage_range(self, voltage_range):
            self.voltage_range=abs(voltage_range)
        def get_voltage_range(self):
            return self.voltage_range
        
        _terms={"default":nidaqmx.constants.TerminalConfiguration.DEFAULT,
                "diff":nidaqmx.constants.TerminalConfiguration.DIFFERENTIAL,
                "dseudodiff":nidaqmx.constants.TerminalConfiguration.PSEUDODIFFERENTIAL,
                "rse":nidaqmx.constants.TerminalConfiguration.RSE,
                "nrse":nidaqmx.constants.TerminalConfiguration.NRSE}
        def read_channel(self, channel, terminal='diff', points=1E3):
            conseq_fails=0
            for t in general.RetryOnException(self._retry_times,RuntimeError):
                with t:
                    task=nidaqmx.Task()
                    task.ai_channels.add_ai_voltage_chan('{0}/ai{1:d}'.format(self.dev,channel),
                        terminal_config=self._terms[terminal],min_val=-self.voltage_range,max_val=self.voltage_range)
                    task.timing.cfg_samp_clk_timing(rate=self.rate,sample_mode=nidaqmx.constants.AcquisitionType.FINITE,samps_per_chan=int(points))
                    task.start()
                    task.wait_until_done()
                    data=task.read(int(points))
                    task.stop()
                    task.close()
                    return np.array(data)
                conseq_fails=conseq_fails+1
                if conseq_fails>2:
                    error_msg="Failure to access NIUSB6009 {} times in a row; retrying...".format(conseq_fails)
                    log.default_log.info(error_msg,origin="devices/NIUSB6009",level="warning")
                time.sleep(self._retry_delay)
except ImportError:
    pass