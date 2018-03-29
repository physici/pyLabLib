from ...core.devio import backend as backend_mod  #@UnresolvedImport

import re

_depends_local=["...core.devio.backend"]


class AttocubeError(RuntimeError):
    """Generic Attocube error."""

class ANCDevice(backend_mod.IBackendWrapper):
    """
    Generic Attocube ANC controller.
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

    def open(self):
        """Open the backend."""
        res=self.instr.open()
        if self.instr._backend=="network":
            self.instr.write(self.pwd)
        self.instr.write("echo off")
        self.instr.flush_read()
        self.update_available_axes()
        return res
    
    def query(self, msg):
        self.instr.flush_read()
        self.instr.write(msg)
        reply=self.instr.read_multichar_term(["ERROR","OK"],remove_term=False)
        self.instr.flush_read()
        if reply.upper().endswith("ERROR"):
            raise AttocubeError(reply[:-5].strip())
        return reply[:-2].strip()
    
    def update_available_axes(self):
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
        if axis=="all":
            for ax in self.axes:
                self.set_mode(ax,mode)
            return
        self.query("setm {} {}".format(axis,mode))
    def enable_all(self, mode="stp"):
        self.set_mode("all",mode=mode)
    def disable_all(self):
        self.set_mode("all",mode="gnd")

    def _parse_reply(self, reply, name, units):
        patt=name+r"\s*=\s*([\d.]+)\s*"+units
        m=re.match(patt,reply,re.IGNORECASE)
        if not m:
            raise AttocubeError("unexpected reply: {}".format(reply))
        return float(m.groups()[0])
    def get_voltage(self, axis):
        reply=self.query("getv {}".format(axis))
        return self._parse_reply(reply,"voltage","V")
    def set_voltage(self, axis, voltage):
        self.query("setv {} {}".format(axis,voltage))
        return self.get_voltage(axis)
    def get_offset(self, axis):
        reply=self.query("geta {}".format(axis))
        return self._parse_reply(reply,"voltage","V")
    def set_offset(self, axis, voltage):
        self.query("seta {} {}".format(axis,voltage))
        return self.get_offset(axis)
    def get_output(self, axis):
        reply=self.query("geto {}".format(axis))
        return self._parse_reply(reply,"voltage","V")
    def get_frequency(self, axis):
        reply=self.query("getf {}".format(axis))
        return self._parse_reply(reply,"frequency","Hz")
    def set_frequency(self, axis, freq):
        self.query("setf {} {}".format(axis,freq))
        return self.get_frequency(axis)

    def set_axis_correction(self, axis, factor=1.):
        self._correction[axis]=factor
    def move(self, axis, steps=1):
        if steps<0:
            steps*=self._correction.get(axis,1.)
        steps=int(steps)
        if not steps:
            return
        comm="stepu" if steps>0 else "stepd"
        self.query("{} {} {}".format(comm,axis,abs(steps)))
    def wait_for_axis(self, axis, timeout=30.):
        with self.instr.using_timeout(timeout):
            self.query("stepw {}".format(axis))
    def is_moving(self, axis):
        return self.get_output(axis)!=0.
    def stop(self, axis="all"):
        if axis=="all":
            for ax in self.axes:
                self.stop(ax)
            return
        self.query("stop {}".format(axis))