from ...core.devio import backend as backend_mod  #@UnresolvedImport
from ...core.utils import py3

import re

_depends_local=["...core.devio.backend"]


class AttocubeError(RuntimeError):
    """Generic Attocube error"""

class ANCDevice(backend_mod.IBackendWrapper):
    """
    Generic Attocube ANC controller.

    Args:
        conn: connection parameters; for Ethernet connection is a tuple ``(addr, port)`` or a string ``"addr:port"``
        backend(str): communication backend; by default, try to determine from the communication parameters
        pwd(str): connection password for Ethernet connection (default is ``"123456"``)
    """
    def __init__(self, conn, backend="auto", pwd="123456"):
        if backend=="auto":
            backend=backend_mod.autodetect_backend(conn)
        if backend=="network":
            conn=backend_mod.NetworkDeviceBackend.combine_conn(conn,{"port":7230})
        instr=backend_mod.new_backend(conn,backend=backend,timeout=3.,term_write="\r\n")
        self.pwd=pwd
        backend_mod.IBackendWrapper.__init__(self,instr)
        self.open()
        self._correction={}
        self._add_settings_node("voltages",self.get_all_voltages,self.set_all_voltages)
        self._add_settings_node("offsets",self.get_all_offsets,self.set_all_offsets)
        self._add_settings_node("frequencies",self.get_all_frequencies,self.set_all_frequencies)

    def open(self):
        """Open the connection to the stage"""
        res=self.instr.open()
        if self.instr._backend=="network":
            self.instr.write(self.pwd)
        self.instr.write("echo off")
        self.instr.flush_read()
        self.update_available_axes()
        return res
    
    def query(self, msg):
        """Send a query to the stage and return the reply"""
        self.instr.flush_read()
        self.instr.write(msg)
        reply=self.instr.read_multichar_term(["ERROR","OK"],remove_term=False)
        self.instr.flush_read()
        if reply.upper().endswith(b"ERROR"):
            raise AttocubeError(reply[:-5].strip())
        return reply[:-2].strip()
    
    def update_available_axes(self):
        """
        Update the list of available axes.
        
        Need to call only if the hardware configuration of the ANC module has changed.
        """
        axes=[]
        for ax in range(1,8):
            try:
                self.query("getm {}".format(ax))
                axes.append(ax)
            except AttocubeError:
                pass
        self.axes=list(axes)
        return axes

    def set_mode(self, axis="all", mode="stp"):
        """
        Set axis mode.

        `axis` is either an axis index (starting from 1), or ``"all"`` (all axes).
        `mode` is ``"gnd"`` (ground) or ``"stp"`` (step).
        """
        if axis=="all":
            for ax in self.axes:
                self.set_mode(ax,mode)
            return
        self.query("setm {} {}".format(axis,mode))
    def enable_all(self, mode="stp"):
        """Enable all axes (set to step mode)"""
        self.set_mode("all",mode=mode)
    def disable_all(self):
        """Disable all axes (set to ground mode)"""
        self.set_mode("all",mode="gnd")

    def _parse_reply(self, reply, name, units):
        patt=name+r"\s*=\s*([\d.]+)\s*"+units
        reply=py3.as_str(reply)
        m=re.match(patt,reply,re.IGNORECASE)
        if not m:
            raise AttocubeError("unexpected reply: {}".format(reply))
        return float(m.groups()[0])
    def get_voltage(self, axis):
        """Get axis step voltage in Volts"""
        reply=self.query("getv {}".format(axis))
        return self._parse_reply(reply,"voltage","V")
    def set_voltage(self, axis, voltage):
        """Set axis step voltage in Volts"""
        self.query("setv {} {}".format(axis,voltage))
        return self.get_voltage(axis)
    def get_offset(self, axis):
        """Get axis offset voltage in Volts"""
        reply=self.query("geta {}".format(axis))
        return self._parse_reply(reply,"voltage","V")
    def set_offset(self, axis, voltage):
        """Set axis offset voltage in Volts"""
        self.query("seta {} {}".format(axis,voltage))
        return self.get_offset(axis)
    def get_output(self, axis):
        """Get axis curent output voltage in Volts"""
        reply=self.query("geto {}".format(axis))
        return self._parse_reply(reply,"voltage","V")
    def get_frequency(self, axis):
        """Get axis step frequency in Hz"""
        reply=self.query("getf {}".format(axis))
        return self._parse_reply(reply,"frequency","Hz")
    def set_frequency(self, axis, freq):
        """Set axis step frequency in Hz"""
        self.query("setf {} {}".format(axis,freq))
        return self.get_frequency(axis)

    def _get_all_axes_data(self, getter):
        return dict([(a,getter(a)) for a in self.axes])
    def get_all_voltages(self):
        """Get the list of all axes step voltages"""
        return self._get_all_axes_data(self.get_voltage)
    def get_all_offsets(self):
        """Get the list of all axes offset voltages"""
        return self._get_all_axes_data(self.get_offset)
    def get_all_frequencies(self):
        """Get the list of all axes step frequencies"""
        return self._get_all_axes_data(self.get_frequency)
    
    def _set_all_axes_data(self, setter, values):
        if isinstance(values,(tuple,list)):
            values=dict(zip([self.axes,values]))
        for a,v in values.items():
            setter(a,v)
    def set_all_voltages(self, voltages):
        """
        Get all axes step voltages.
        
        `voltages` is a list of step voltage, whose length is equal to the number of active (connected) axes.
        """
        self._set_all_axes_data(self.set_voltage,voltages)
        return self.get_all_voltages()
    def set_all_offsets(self, offsets):
        """
        Get all axes offset voltages
        
        `offsets` is a list of offset voltags, whose length is equal to the number of active (connected) axes.
        """
        self._set_all_axes_data(self.set_offset,offsets)
        return self.get_all_offsets()
    def set_all_frequencies(self, frequencies):
        """
        Get all axes step frequencies
        
        `frequencies` is a list of step frequencies, whose length is equal to the number of active (connected) axes.
        """
        self._set_all_axes_data(self.set_frequency,frequencies)
        return self.get_all_frequencies()

    def set_axis_correction(self, axis, factor=1.):
        """
        Set axis correction factor.

        The factor is automatically applied when the motion is in the negative direction.
        """
        self._correction[axis]=factor
    def move(self, axis, steps=1):
        """Move a given axis for a given number of steps"""
        if steps<0:
            steps*=self._correction.get(axis,1.)
        steps=int(steps)
        if not steps:
            return
        comm="stepu" if steps>0 else "stepd"
        self.query("{} {} {}".format(comm,axis,abs(steps)))
    def wait_for_axis(self, axis, timeout=30.):
        """
        Wait for a given axis to stop moving.

        If the motion is not finsihed after `timeout` seconds, raise a backend error.
        """
        with self.instr.using_timeout(timeout):
            self.query("stepw {}".format(axis))
    def is_moving(self, axis):
        """Check if a given axis is moving"""
        return self.get_output(axis)!=0.
    def stop(self, axis):
        """Stop motion of a given axis"""
        self.query("stop {}".format(axis))
    def stop_all(self):
        """Stop motion of all axes"""
        for ax in self.axes:
            self.stop(ax)
