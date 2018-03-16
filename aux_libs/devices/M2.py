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
    def __init__(self, addr, port, timeout=3., start_link=True, use_websocket=True):
        object.__init__(self)
        self.tx_id=1
        self.conn=(addr,port)
        self.timeout=timeout
        self.open()
        if start_link:
            self.start_link()
        self._last_status={}
        self.use_websocket=use_websocket and (websocket is not None)

    def open(self):
        self.socket=net.ClientSocket(send_method="fixedlen",recv_method="fixedlen",timeout=self.timeout)
        self.socket.connect(*self.conn)
        self._last_status={}
    def close(self):
        self.socket.close()

    def __enter__(self):
        return self
    def __exit__(self, *args, **vargs):
        self.close()
        return False

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
    
    def _recv_reply(self, expected=None):
        while True:
            reply=net.recv_JSON(self.socket)
            preply=self._parse_reply(reply)
            if preply[0].endswith("_f_r") and preply[0]!=expected:
                self._last_status[preply[0][:-4]]=preply[1]
            else:
                return preply
    def flush(self):
        self.socket.recv_all()
    def query(self, op, params, reply_op="auto", report=False):
        if report:
            params["report"]="finished"
            self._last_status[op]=None
        msg=self._build_message(op,params)
        self.socket.send(msg)
        preply=self._recv_reply()
        if reply_op=="auto":
            reply_op=op+"_reply"
        if reply_op and preply[0]!=reply_op:
            raise M2Error("unexpected reply op: '{}' (expected '{}')".format(preply[0],reply_op))
        return preply
    def check_reports(self, timeout=0.):
        timeout=max(timeout,0.001)
        try:
            with self.socket.using_timeout(timeout):
                preport=self._recv_reply()
                raise M2Error("received reply while waiting for a report: '{}'".format(preport[0]))
        except net.SocketTimeout:
            pass
    def get_last_report(self, op):
        rep=self._last_status.get(op,None)
        if rep:
            return "fail" if rep["report"][0] else "success"
        return None
    def wait_for_report(self, op, error_msg=None, timeout=None):
        with self.socket.using_timeout(timeout):
            preport=self._recv_reply(expected=op+"_f_r")
            if not preport[0].endswith("_f_r"):
                raise M2Error("unexpected report op: '{}'".format(preport[0]))
        if preport[1]["report"][0]!=0:
            if error_msg is None:
                error_msg="error on operation {}; error report {}".format(preport[0][:-4],preport[1])
            raise M2Error(error_msg)
        return preport


    def start_link(self):
        reply=self.query("start_link",{"ip_address":self.socket.get_local_name()[0]})[1]
        if reply["status"]!="ok":
            raise M2Error("couldn't establish link: reply status '{}'".format(reply["status"]))

    def _send_websocket_request(self, msg):
        if self.use_websocket:
            ws=websocket.create_connection("ws://{}:8088/control.htm".format(self.conn[0]),timeout=5.)
            time.sleep(1.)
            ws.send(msg)
            ws.close()
        else:
            raise RuntimeError("'websocket' library is requried to communicate this request")
    def _read_websocket_status(self):
        if self.use_websocket:
            ws=websocket.create_connection("ws://{}:8088/control.htm".format(self.conn[0]),timeout=5.)
            data=ws.recv()
            ws.close()
            return json.loads(data)
        else:
            raise RuntimeError("'websocket' library is requried to communicate this request")
    def connect_wavemeter(self):
        self._send_websocket_request('{"message_type":"task_request","task":["start_wavemeter_link"]}')
    def disconnect_wavemeter(self):
        self._send_websocket_request('{"message_type":"task_request","task":["job_stop_wavemeter_link"]}')

    def get_system_status(self):
        _,reply=self.query("get_status",{})
        for k in reply:
            if isinstance(reply[k],list):
                reply[k]=reply[k][0]
        return reply
    def get_full_web_status(self):
        return self._read_websocket_status()
    def _as_web_status(self, status):
        if status=="auto":
            status="new" if self.use_websocket else None
        if status=="new":
            return self.get_full_web_status()
        if status is None:
            return None
        return status
    
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
            self.wait_for_report("set_wave_m",timeout=timeout)
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
            self.wait_for_report("move_wave_t")
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
            self.wait_for_report("tune_etalon")
    def lock_etalon(self, sync=True):
        _,reply=self.query("etalon_lock",{"operation":"on"},report=sync)
        if reply["status"][0]==1:
            raise M2Error("can't lock etalon")
        if sync:
            self.wait_for_report("etalon_lock")
    def unlock_etalon(self, sync=True):
        self.unlock_reference_cavity(sync=True)
        _,reply=self.query("etalon_lock",{"operation":"off"},report=sync)
        if reply["status"][0]==1:
            raise M2Error("can't unlock etalon")
        if sync:
            self.wait_for_report("etalon_lock")
    def get_etalon_lock_status(self):
        _,reply=self.query("etalon_lock_status",{})
        if reply["status"][0]==1:
            raise M2Error("can't get etalon status")
        return reply["condition"]

    def tune_reference_cavity(self, perc, fine=False, sync=True):
        _,reply=self.query("fine_tune_cavity" if fine else "tune_cavity",{"setting":[perc]},report=sync)
        if reply["status"][0]==1:
            raise M2Error("can't tune reference cavity: {} is out of range".format(perc))
        elif reply["status"][0]==2:
            raise M2Error("can't tune reference cavity: command failed")
        if sync:
            self.wait_for_report("fine_tune_cavity")
    def lock_reference_cavity(self, sync=True):
        self.lock_etalon(sync=True)
        _,reply=self.query("cavity_lock",{"operation":"on"},report=sync)
        if reply["status"][0]==1:
            raise M2Error("can't lock reference cavity")
        if sync:
            self.wait_for_report("cavity_lock")
    def unlock_reference_cavity(self, sync=True):
        _,reply=self.query("cavity_lock",{"operation":"off"},report=sync)
        if reply["status"][0]==1:
            raise M2Error("can't unlock reference cavity")
        if sync:
            self.wait_for_report("cavity_lock")
    def get_reference_cavity_lock_status(self):
        _,reply=self.query("cavity_lock_status",{})
        if reply["status"][0]==1:
            raise M2Error("can't get etalon status")
        return reply["condition"]

    def tune_laser_resonator(self, perc, fine=False, sync=True):
        _,reply=self.query("fine_tune_resonator" if fine else "tune_resonator",{"setting":[perc]},report=sync)
        if reply["status"][0]==1:
            raise M2Error("can't tune resonator: {} is out of range".format(perc))
        elif reply["status"][0]==2:
            raise M2Error("can't tune resonator: command failed")
        if sync:
            self.wait_for_report("fine_tune_resonator")

    
    def _check_terascan_type(self, scan_type):
        if scan_type not in {"coarse","medium","fine","line"}:
            raise M2Error("unknown TeraScan type: {}".format(scan_type))
        if scan_type=="coarse":
            raise M2Error("coarse scan is not currently available")
    def setup_terascan(self, scan_type, scan_range, rate):
        self._check_terascan_type(scan_type)
        if rate>=1E9:
            fact,units=1E9,"GHz/s"
        elif rate>=1E6:
            fact,units=1E6,"MHz/s"
        else:
            fact,units=1E3,"kHz/s"
        params={"scan":scan_type,"start":[c/scan_range[0]*1E9],"stop":[c/scan_range[1]*1E9],"rate":[rate/fact],"units":units}
        _,reply=self.query("scan_stitch_initialise",params)
        if reply["status"][0]==1:
            raise M2Error("can't setup TeraScan: start ({:.3f} THz) is out of range".format(scan_range[0]/1E12))
        elif reply["status"][0]==2:
            raise M2Error("can't setup TeraScan: stop ({:.3f} THz) is out of range".format(scan_range[1]/1E12))
        elif reply["status"][0]==3:
            raise M2Error("can't setup TeraScan: scan out of range")
        elif reply["status"][0]==4:
            raise M2Error("can't setup TeraScan: TeraScan not available")
    def start_terascan(self, scan_type, sync=False):
        self._check_terascan_type(scan_type)
        _,reply=self.query("scan_stitch_op",{"scan":scan_type,"operation":"start"},report=True)
        if reply["status"][0]==1:
            raise M2Error("can't start TeraScan: operation failed")
        elif reply["status"][0]==2:
            raise M2Error("can't start TeraScan: TeraScan not available")
        if sync:
            self.wait_for_report("scan_stitch_op")
    def check_terascan_report(self):
        self.check_reports()
        return self.get_last_report("scan_stitch_op")
    def stop_terascan(self, scan_type, sync=False):
        self._check_terascan_type(scan_type)
        _,reply=self.query("scan_stitch_op",{"scan":scan_type,"operation":"stop"},report=sync)
        if reply["status"][0]==1:
            raise M2Error("can't stop TeraScan: operation failed")
        elif reply["status"][0]==2:
            raise M2Error("can't stop TeraScan: TeraScan not available")
        if sync:
            self.wait_for_report("scan_stitch_op")
    _web_scan_status_str=['off','cont','single','flyback','on','fail']
    def get_terascan_status(self, scan_type, web_status="auto"):
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
            status["current"]=c/(reply["current"][0]/1E9)
        elif reply["status"][0]==2:
            raise M2Error("can't stop TeraScan: TeraScan not available")
        web_status=self._as_web_status(web_status)
        if web_status:
            status["web"]=self._web_scan_status_str[web_status["scan_status"]]
        else:
            status["web"]=None
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
            self.wait_for_report("fast_scan_start")
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
            self.wait_for_report("fast_scan_stop")
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
    _default_terascan_rates={"line":10E6,"fine":100E6,"medium":5E9}
    def stop_all_operation(self, repeated=True):
        attempts=0
        while True:
            operating=False
            for scan_type in ["medium","fine","line"]:
                stat=self.get_terascan_status(scan_type)
                if stat["status"]!="stopped":
                    operating=True
                    self.stop_terascan(scan_type)
                    time.sleep(0.5)
                    if attempts>3:
                        self.stop_scan_web(scan_type)
                    if attempts>6:
                        rate=self._default_terascan_rates[scan_type]
                        self.setup_terascan(scan_type,(stat["current"],stat["current"]+rate*10),rate)
                        self.start_terascan(scan_type)
                        time.sleep(1.)
                        self.stop_terascan(scan_type)
            for scan_type in self._fast_scan_types:
                try:
                    if self.get_fast_scan_status(scan_type)["status"]!="stopped":
                        operating=True
                        self.stop_fast_scan(scan_type)
                        time.sleep(0.5)
                        if attempts>3:
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