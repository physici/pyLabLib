from ...core.utils import net

import json

class M2ICE(object):
    def __init__(self, addr, port, timeout=3.):
        object.__init__(self)
        self.tx_id=1
        self.socket=net.ClientSocket(send_method="fixedlen",recv_method="fixedlen",timeout=timeout)
        self.conn=(addr,port)
        self.socket.connect(addr,port)

    def _build_message(self, op, params, tx_id=None):
        if tx_id is None:
            tx_id=self.tx_id
            self.tx_id+=1
        msg={"message":{"transmission_id":[tx_id],"op":op,"parameters":dict(params)}}
        return json.dumps(msg)
    def _parse_message(self, msg):
        pmsg=json.loads(msg)
        if "message" not in pmsg:
            raise RuntimeError("coudn't decode message: {}".format(msg))
        pmsg=pmsg["message"]
        for key in ["transmission_id", "op", "parameters"]:
            if key not in pmsg:
                raise RuntimeError("parameter '{}' not in the message {}".format(key,msg))
        return pmsg
    _parse_errors=["unknown", "JSON parsing error", "'message' string missing",
                             "'transimssion_id' string missing", "No 'transmission_id' value",
                             "'op' string missing", "No operation name",
                             "operation not recognized", "'parameters' string missing", "invalid parameter tag or value"]
    def _parse_reply(self, msg):
        pmsg=self._parse_message(msg)
        if pmsg["op"]=="parse_failure":
            par=msg["parameters"]
            perror=par["protocol_error"]
            perror_desc="unknown" if perror>len(self._parse_errors) else self._parse_errors[perror]
            error_msg="device parse error: transmission_id={}, error={}({}), error point='{}'".format(
                par["transmission"],perror,perror_desc,par["JSON_parse_error"])
            raise RuntimeError(error_msg)
        return pmsg["op"],pmsg["parameters"],pmsg["transmission_id"][0]
    
    def query(self, op, params, tx_id=None, reply_op=None):
        msg=self._build_message(op,params,tx_id=tx_id)
        self.socket.send(msg)
        reply=net.recv_JSON(self.socket)
        preply=self._parse_reply(reply)
        if reply_op and preply[0]!=reply_op:
            raise RuntimeError("unexpected reply op: '{}' (expected '{}')",format(preply[0],reply_op))
        return preply


    def start_link(self):
        reply=self.query("start_link",{"ip_address":self.socket.get_local_name()[0]},reply_op="start_link_reply")[1]
        if reply["status"]!="ok":
            raise RuntimeError("couldn't establish link: reply status '{}'".format(reply["status"]))
    
    