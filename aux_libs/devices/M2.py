from ...core.utils import net

import json


class M2Error(RuntimeError):
    """
    M2 communication error.
    """
    pass
class M2ICE(object):
    def __init__(self, addr, port, timeout=3.):
        object.__init__(self)
        self.tx_id=1
        self.conn=(addr,port)
        self.timeout=timeout
        self.open()

    def open(self):
        self.socket=net.ClientSocket(send_method="fixedlen",recv_method="fixedlen",timeout=self.timeout)
        self.socket.connect(*self.conn)
    def close(self):
        self.socket.close()

    def _build_message(self, op, params, tx_id=None):
        if tx_id is None:
            tx_id=self.tx_id
            self.tx_id=self.tx_id%16383+1
        msg={"message":{"transmission_id":[tx_id],"op":op,"parameters":dict(params)}}
        return json.dumps(msg)
    def _parse_message(self, msg):
        pmsg=json.loads(msg)
        if "message" not in pmsg:
            raise M2Error("coudn't decode message: {}".format(msg))
        pmsg=pmsg["message"]
        for key in ["transmission_id", "op", "parameters"]:
            if key not in pmsg:
                raise M2Error("parameter '{}' not in the message {}".format(key,msg))
        return pmsg
    _parse_errors=["unknown", "JSON parsing error", "'message' string missing",
                             "'transimssion_id' string missing", "No 'transmission_id' value",
                             "'op' string missing", "No operation name",
                             "operation not recognized", "'parameters' string missing", "invalid parameter tag or value"]
    def _parse_reply(self, msg):
        pmsg=self._parse_message(msg)
        if pmsg["op"]=="parse_fail":
            print(pmsg)
            par=pmsg["parameters"]
            perror=par["protocol_error"][0]
            perror_desc="unknown" if perror>=len(self._parse_errors) else self._parse_errors[perror]
            error_msg="device parse error: transmission_id={}, error={}({}), error point='{}'".format(
                par.get("transmission",["NA"])[0],perror,perror_desc,par.get("JSON_parse_error","NA"))
            raise M2Error(error_msg)
        return pmsg["op"],pmsg["parameters"]
    
    def flush(self):
        self.socket.recv_all()
    def query(self, op, params, reply_op="auto", report=False):
        if report:
            params["report"]="finished"
        msg=self._build_message(op,params)
        self.socket.send(msg)
        reply=net.recv_JSON(self.socket)
        preply=self._parse_reply(reply)
        if reply_op=="auto":
            reply_op=op+"_reply"
        if reply_op and preply[0]!=reply_op:
            raise M2Error("unexpected reply op: '{}' (expected '{}')".format(preply[0],reply_op))
        return preply

    def wait_for_report(self, timeout=None):
        with self.socket.using_timeout(timeout):
            report=net.recv_JSON(self.socket)
            preport=self._parse_reply(report)
            if not preport[0].endswith("_f_r"):
                raise M2Error("unexpected report op: '{}'".format(preport[0]))
        return preport


    def start_link(self):
        reply=self.query("start_link",{"ip_address":self.socket.get_local_name()[0]})[1]
        if reply["status"]!="ok":
            raise M2Error("couldn't establish link: reply status '{}'".format(reply["status"]))

    def get_system_status(self):
        return self.query("get_status",{})[1]
    
    def get_full_tuning_status(self):
        return self.query("poll_wave_m",{})[1]
    def lock_wavemeter(self, lock=True):
        _,reply=self.query("lock_wave_m",{"operation":"on" if lock else "off"})
        if reply["status"][0]==1:
            raise M2Error("can't lock wavemeter: no wavemeter link")
    def is_wavelemeter_lock_on(self):
        return self.get_full_tuning_status()["lock_status"][0]

    def tune_wavelength(self, wavelength, sync=True, timeout=None):
        _,reply=self.query("set_wave_m",{"wavelength":[wavelength*1E9]},report=sync)
        if reply["status"][0]==1:
            raise M2Error("can't tune wavelength: no wavemeter link")
        elif reply["status"][0]==2:
            raise M2Error("can't tune wavelength: {}nm is out of range".format(wavelength*1E9))
        if sync:
            self.wait_for_report(timeout=timeout)
    def get_tuning_status(self):
        status=self.get_full_tuning_status()["status"][0]
        return ["off","nolink","tuning","on"][status]
    def get_wavelength(self):
        return self.get_full_tuning_status()["current_wavelength"][0]*1E-9
    def stop_tuning(self):
        _,reply=self.query("stop_wave_m",{})
        if reply["status"][0]==1:
            raise M2Error("can't stop tuning: no wavemeter link")

    def tune_wavelength_table(self, wavelength, sync=True):
        _,reply=self.query("move_wave_t",{"wavelength":[wavelength*1E9]},report=sync)
        if reply["status"][0]==1:
            raise M2Error("can't tune etalon: command failed")
        elif reply["status"][0]==2:
            raise M2Error("can't tune wavelength: {}nm is out of range".format(wavelength*1E9))
        if sync:
            self.wait_for_report()
    def get_full_tuning_status_table(self):
        return self.query("poll_move_wave_t",{})[1]
    def get_tuning_status_table(self):
        status=self.get_full_tuning_status_table()["status"][0]
        return ["done","tuning","fail"][status]
    def get_wavelength_table(self):
        return self.get_full_tuning_status_table()["current_wavelength"][0]*1E-9
    def stop_tuning_table(self):
        _,reply=self.query("stop_move_wave_t",{})

    def tune_etalon(self, perc, sync=True):
        _,reply=self.query("tune_etalon",{"setting":[perc]},report=sync)
        if reply["status"][0]==1:
            raise M2Error("can't tune etalon: {} is out of range".format(perc))
        elif reply["status"][0]==2:
            raise M2Error("can't tune etalon: command failed")
        if sync:
            self.wait_for_report()