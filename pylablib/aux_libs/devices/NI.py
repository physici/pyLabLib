from ...core.devio import backend  #@UnresolvedImport
from ...core.utils import general, funcargparse  #@UnresolvedImport

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
except ImportError:
    pass

class NIDAQ(object):
    """
    National Instruments DAQ device.
    """
    _default_retry_delay=5.
    _default_retry_times=5
    def __init__(self, dev_name, rate=1E4, buffer_size=1E5):
        object.__init__(self)
        self.dev_name=dev_name.strip("/")
        self.rate=rate
        self.buffer_size=buffer_size
        self.ai_channels={}
        self.ci_tasks={}
        self.ci_counters={}
        self.do_channels={}
        self.ao_channels={}
        self.ao_values={}
        self.open()
        self._update_channel_names()
        self._running=False
        
    def open(self):
        self.ai_task=nidaqmx.Task()
        self.do_task=nidaqmx.Task()
        self.ao_task=nidaqmx.Task()
    def close(self):
        if self.ai_task is not None:
            self.ai_task.close()
        self.ai_task=None
        self.ai_channels={}
        for t in self.ci_tasks.values():
            t[0].close()
        self.ci_tasks={}
        if self.do_task is not None:
            self.do_task.close()
        self.do_task=None
        self.do_channels={}
        if self.ao_task is not None:
            self.ao_task.close()
        self.ao_task=None
        self.ao_channels={}
        self.ao_values={}
        self._update_channel_names()

    def __enter__(self):
        self.open()
        return self
    def __exit__(self, *args, **vargs):
        self.close()
        return False

    def _build_channel_name(self, channel):
        channel=channel.lower().strip("/")
        if channel.startswith("dev") or self.dev_name is None:
            return "/"+channel
        return "/"+self.dev_name+"/"+channel
    def _update_channel_names(self):
        self.ai_names=list(self.ai_channels.keys())
        self.ai_names.sort(key=lambda n: self.ai_channels[n][1])
        self.ci_names=list(self.ci_tasks.keys())
        self.ci_names.sort(key=lambda n: self.ci_tasks[n][1])
        self.do_names=list(self.do_channels.keys())
        self.do_names.sort(key=lambda n: self.do_channels[n][1])
        self.ao_names=list(self.ao_channels.keys())
        self.ao_names.sort(key=lambda n: self.ao_channels[n][1])

    def set_sampling_rate(self, rate):
        self.rate=rate
        if self.ai_task.ai_channels:
            self.ai_task.timing.samp_clk_rate=self.rate

    _voltage_input_terms={  "default":nidaqmx.constants.TerminalConfiguration.DEFAULT,
                            "rse":nidaqmx.constants.TerminalConfiguration.RSE,
                            "nrse":nidaqmx.constants.TerminalConfiguration.NRSE,
                            "diff":nidaqmx.constants.TerminalConfiguration.DIFFERENTIAL,
                            "pseudodiff":nidaqmx.constants.TerminalConfiguration.PSEUDODIFFERENTIAL}
    def add_voltage_input(self, name, channel, rng=(-10,10), term_config="default"):
        channel=self._build_channel_name(channel)
        term_config=self._voltage_input_terms[term_config]
        self.ai_task.ai_channels.add_ai_voltage_chan(channel,name,terminal_config=term_config,min_val=rng[0],max_val=rng[1])
        self.ai_task.timing.cfg_samp_clk_timing(self.rate,sample_mode=nidaqmx.constants.AcquisitionType.CONTINUOUS,samps_per_chan=int(self.buffer_size))
        self.ai_channels[name]=(channel,len(self.ai_task.ai_channels))
        self._update_channel_names()
    def add_counter_input(self, name, counter, terminal, clk_src="ai/SampleClock", max_rate=1E7, output_format="rate"):
        funcargparse.check_parameter_range(output_format,"output_format",{"acc","diff","rate"})
        if name in self.ci_tasks:
            self.ci_tasks[name][0].close()
        task=nidaqmx.Task()
        counter=self._build_channel_name(counter)
        terminal=self._build_channel_name(terminal)
        task.ci_channels.add_ci_count_edges_chan(counter)
        task.ci_channels[0].ci_count_edges_term=terminal
        task.timing.cfg_samp_clk_timing(max_rate,self._build_channel_name(clk_src),sample_mode=nidaqmx.constants.AcquisitionType.CONTINUOUS)
        self.ci_tasks[name]=(task,len(self.ci_tasks),output_format)
        self._update_channel_names()
    
    def read(self, n=1, timeout=10.):
        running=True
        if not self._running:
            running=False
            self.start()
        try:
            if n==-1:
                n=self.available_samples()
            ais=self.ai_task.read(n,timeout=timeout)
            if len(self.ai_task.ai_channels)==1:
                ais=[ais]
            cis=[np.array(self.ci_tasks[ci][0].read(n)) for ci in self.ci_names]
            for i,ci in enumerate(self.ci_names):
                if self.ci_tasks[ci][2]!="acc":
                    last_cnt=cis[i][-1]
                    cis[i][1:]-=cis[i][:-1]
                    cis[i][0]-=self.ci_counters[ci]
                    self.ci_counters[ci]=last_cnt
                    if self.ci_tasks[ci][2]=="rate":
                        cis[i]=cis[i]*self.rate
            return np.column_stack(ais+cis)
        finally:
            if not running:
                self.stop()
    def get_input_channels(self):
        return self.ai_names+self.ci_names
    def start(self, flush_read=0):
        for cit in self.ci_tasks:
            self.ci_tasks[cit][0].start()
            self.ci_counters[cit]=0
        self.ai_task.start()
        self._running=True
        if flush_read:
            self.read(flush_read)
    def stop(self):
        self.ai_task.stop()
        for cit in self.ci_tasks:
            self.ci_tasks[cit][0].stop()
            self.ci_counters[cit]=0
        self._running=False
    def is_running(self):
        return not self._running
    def available_samples(self):
        if not self._running:
            return 0
        return self.ai_task.in_stream.avail_samp_per_chan
    def get_buffer_size(self):
        return self.ai_task.in_stream.input_buf_size if len(self.ai_task.ai_channels) else 0
    def wait_for_sample(self, num=1, timeout=10., wait_time=0.001):
        if not self._running:
            return 0
        if self.available_samples()>=num:
            return self.available_samples()
        ctd=general.Countdown(timeout)
        while not ctd.passed():
            time.sleep(wait_time)
            if self.available_samples()>=num:
                return self.available_samples()
        return 0

    def add_digital_output(self, name, channel):
        channel=self._build_channel_name(channel)
        self.do_task.do_channels.add_do_chan(channel,name)
        self.do_channels[name]=(channel,len(self.do_task.do_channels))
        self._update_channel_names()
    def set_digital_outputs(self, names, values):
        names=funcargparse.as_sequence(names,allowed_type="array")
        values=funcargparse.as_sequence(values,allowed_type="array")
        values_dict=dict(zip(names,values))
        curr_vals=self.do_task.read()
        if len(self.do_task.do_channels)==1:
            curr_vals=[curr_vals]
        for i,ch in enumerate(self.do_task.do_channels):
            if ch.name in values_dict:
                curr_vals[i]=bool(values_dict[ch.name])
        self.do_task.write(curr_vals)
    def get_digital_outputs(self, names=None):
        if names is None:
            names=self.do_names
        else:
            names=funcargparse.as_sequence(names,allowed_type="array")
        values_dict=dict(zip(names,[None]*len(names)))
        curr_vals=self.do_task.read()
        if len(self.do_task.do_channels)==1:
            curr_vals=[curr_vals]
        for i,ch in enumerate(self.do_task.do_channels):
            if ch.name in values_dict:
                values_dict[ch.name]=curr_vals[i]
        return [values_dict[n] for n in names]
    def get_digital_output_channels(self):
        return self.do_names

    def add_voltage_output(self, name, channel, rng=(-10,10), initial_value=0.):
        channel=self._build_channel_name(channel)
        self.ao_task.ao_channels.add_ao_voltage_chan(channel,name,min_val=rng[0],max_val=rng[1])
        self.ao_channels[name]=(channel,len(self.ao_task.ao_channels))
        self.ao_values[name]=initial_value
        self._update_channel_names()
        self.set_voltage_outputs([],[])
    def set_voltage_outputs(self, names, values):
        names=funcargparse.as_sequence(names,allowed_type="array")
        values=funcargparse.as_sequence(values,allowed_type="array")
        for n,v in zip(names,values):
            self.ao_values[n]=v
        self.ao_task.write([self.ao_values[ch.name] for ch in self.ao_task.ao_channels])
    def get_voltage_outputs(self, names=None):
        if names is None:
            names=self.ao_names
        else:
            names=funcargparse.as_sequence(names,allowed_type="array")
        return [self.ao_values[n] for n in names]
    def get_voltage_output_channels(self):
        return self.ao_names