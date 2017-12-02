from ...core.utils import net

try:
    import websocket
except ImportError:
    websocket=None

import json
import time


c=299792458.

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

    def _send_websocket_request(self, msg):
        if websocket:
            ws=websocket.create_connection("ws://{}:8088/control.htm".format(self.conn[0]),timeout=5.)
            time.sleep(1.)
            ws.send(msg)
            ws.close()
        else:
            raise RuntimeError("'websocket' library is requried to communicate this request")
    def connect_wavemeter(self):
        self._send_websocket_request('{"message_type":"task_request","task":["start_wavemeter_link"]}')
    def disconnect_wavemeter(self):
        self._send_websocket_request('{"message_type":"task_request","task":["job_stop_wavemeter_link"]}')

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
        return ["lock_off","nolink","tuning","done"][status]
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

    
    def _check_terascan_type(self, scan_type):
        if scan_type not in {"coarse","medium","fine","line"}:
            raise M2Error("unknown TeraScan type: {}".format(scan_type))
        if scan_type=="coarse":
            raise M2Error("coarse scan is not currently available")
    def setup_terascan(self, scan_type, scan_range, rate, sync=True):
        self._check_terascan_type(scan_type)
        if scan_type=="medium":
            fact,units=1E9,"GHz/s"
        elif scan_type=="fine":
            fact,units=1E6,"MHz/s"
        elif scan_type=="line":
            fact,units=1E3,"kHz/s"
        params={"scan":scan_type,"start":[c/scan_range[0]*1E9],"stop":[c/scan_range[0]*1E9],"rate":[rate/fact],"units":units}
        _,reply=self.query("scan_stitch_initialise",params,report=sync)
        if reply["status"][0]==1:
            raise M2Error("can't setup TeraScan: start ({:.3f} THz) is out of range".format(scan_range[0]/1E12))
        elif reply["status"][0]==2:
            raise M2Error("can't setup TeraScan: stop ({:.3f} THz) is out of range".format(scan_range[1]/1E12))
        elif reply["status"][0]==2:
            raise M2Error("can't setup TeraScan: stop ({:.3f} THz) is out of range".format(scan_range[1]/1E12))
        elif reply["status"][0]==3:
            raise M2Error("can't setup TeraScan: scan out of range")
        elif reply["status"][0]==4:
            raise M2Error("can't setup TeraScan: TeraScan not available")
        if sync:
            self.wait_for_report()
    def start_terascan(self, scan_type, sync=False):
        self._check_terascan_type(scan_type)
        _,reply=self.query("scan_stitch_op",{"scan":scan_type,"operation":"start"},report=sync)
        if reply["status"][0]==1:
            raise M2Error("can't start TeraScan: operation failed")
        elif reply["status"][0]==2:
            raise M2Error("can't start TeraScan: TeraScan not available")
        if sync:
            self.wait_for_report()
    def stop_terascan(self, scan_type, sync=True):
        self._check_terascan_type(scan_type)
        _,reply=self.query("scan_stitch_op",{"scan":scan_type,"operation":"stop"},report=sync)
        if reply["status"][0]==1:
            raise M2Error("can't stop TeraScan: operation failed")
        elif reply["status"][0]==2:
            raise M2Error("can't stop TeraScan: TeraScan not available")
        if sync:
            self.wait_for_report()
    def get_terascan_status(self, scan_type):
        self._check_terascan_type(scan_type)
        _,reply=self.query("scan_stitch_status",{"scan":scan_type})
        status={}
        if reply["status"][0]==0:
            status["status"]="stopped"
            status["range"]=None
        elif reply["status"][0]==1:
            if reply["operation"][0]==0:
                status["status"]="stitching"
            elif reply["operation"][0]==1:
                status["status"]="scanning"
            status["range"]=c/(reply["start"][0]/1E9),c/(reply["stop"][0]/1E9)
        elif reply["status"][0]==2:
            raise M2Error("can't stop TeraScan: TeraScan not available")
        return status

    _fast_scan_types={"etalon_continuous","etalon_single",
                "cavity_continuous","cavity_single","cavity_triangular",
                "resonator_continuous","resonator_single","resonator_ramp","resonator_triangular",
                "ect_continuous","ecd_ramp",
                "fringe_test"}
    def _check_fast_scan_type(self, scan_type):
        if scan_type not in self._fast_scan_types:
            raise M2Error("unknown fast scan type: {}".format(scan_type))
    def start_fast_scan(self, scan_type, width, time, sync=False):
        self._check_fast_scan_type(scan_type)
        _,reply=self.query("fast_scan_start",{"scan":scan_type,"width":[width/1E9],"time":[time]})
        if reply["status"][0]==1:
            raise M2Error("can't start fast scan: width too great for the current tuning position")
        elif reply["status"][0]==2:
            raise M2Error("can't start fast scan: reference cavity not fitted")
        elif reply["status"][0]==3:
            raise M2Error("can't start fast scan: ERC not fitted")
        elif reply["status"][0]==4:
            raise M2Error("can't start fast scan: invalid scan type")
        elif reply["status"][0]==5:
            raise M2Error("can't start fast scan: time >10000 seconds")
        if sync:
            self.wait_for_report()
    def stop_fast_scan(self, scan_type, return_to_start=True, sync=False):
        self._check_fast_scan_type(scan_type)
        _,reply=self.query("fast_scan_stop" if return_to_start else "fast_scan_stop_nr",{"scan":scan_type})
        if reply["status"][0]==1:
            raise M2Error("can't stop fast scan: operation failed")
        elif reply["status"][0]==2:
            raise M2Error("can't stop fast scan: reference cavity not fitted")
        elif reply["status"][0]==3:
            raise M2Error("can't stop fast scan: ERC not fitted")
        elif reply["status"][0]==4:
            raise M2Error("can't stop fast scan: invalid scan type")
        if sync:
            self.wait_for_report()
    def get_fast_scan_status(self, scan_type):
        self._check_fast_scan_type(scan_type)
        _,reply=self.query("fast_scan_poll",{"scan":scan_type})
        status={}
        if reply["status"][0]==0:
            status["status"]="stopped"
        elif reply["status"][0]==1:
            status["status"]="scanning"
        elif reply["status"][0]==2:
            raise M2Error("can't poll fast scan: reference cavity not fitted")
        elif reply["status"][0]==3:
            raise M2Error("can't poll fast scan: ERC not fitted")
        elif reply["status"][0]==4:
            raise M2Error("can't poll fast scan: invalid scan type")
        status["value"]=reply["tuner_value"][0]
        return status


    def stop_scan_web(self, scan_type):
        try:
            self._check_terascan_type(scan_type)
            scan_type=scan_type+"_scan"
        except M2Error:
            self._check_fast_scan_type(scan_type)
            scan_type=scan_type.replace("continuous","cont")
        scan_task=scan_type+"_stop"
        self._send_websocket_request('{{"message_type":"task_request","task":["{}"]}}'.format(scan_task))

    def stop_all_operation(self, repeated=True):
        attempts=0
        while True:
            operating=False
            for scan_type in ["medium","fine","line"]:
                if self.get_terascan_status(scan_type)["status"]!="stopped":
                    operating=True
                    self.stop_terascan(scan_type)
                    if attempts>1:
                        self.stop_scan_web(scan_type)
            for scan_type in self._fast_scan_types:
                try:
                    if self.get_fast_scan_status(scan_type)["status"]!="stopped":
                        operating=True
                        self.stop_fast_scan(scan_type)
                        if attempts>1:
                            self.stop_scan_web(scan_type)
                except M2Error:
                    pass
            if self.get_tuning_status()=="tuning":
                operating=True
                self.stop_tuning()
            if self.get_tuning_status_table()=="tuning":
                operating=True
                self.stop_tuning_table()
            if (not repeated) or (not operating):
                return
            time.sleep(0.1)
            attempts+=1