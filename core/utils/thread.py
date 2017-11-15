from . import funcargparse

import threading
import Queue


class PeriodicThread(object):
    def __init__(self):
        object.__init__(self)
        self.running=False
        self.paused=False
        self.message_queue=Queue.Queue(1)
        self.ack_queue=Queue.Queue(1)
    
    def execute(self):
        pass
    def process_message(self, msg):
        pass
        
    def loop(self, period, sync):
        self.running=True
        if sync:
            self.ack_queue.put("start")
        try:
            while True:
                try:
                    msg,sync=self.message_queue.get(timeout=period if not self.paused else None)
                    if sync:
                        self.ack_queue.put(msg)
                except Queue.Empty:
                    msg=None
                if msg=="pause":
                    self.paused=True
                elif msg=="resume":
                    self.paused=False
                elif msg=="stop":
                    break
                elif msg is not None:
                    self.process_message(msg)
                if not self.paused:
                    self.execute()
        finally:
            self.running=False
            self.paused=False
        
    def wait_for_execution(self):
        self.send_message(None,sync=True)
    def send_message(self, msg, sync=True):
        if self.running:
            self.message_queue.put((msg,sync))
            if sync:
                ack_msg=self.ack_queue.get()
                if ack_msg!=msg:
                    raise RuntimeError("wrong acknowledgment '{0}' for message '{1}'".format(ack_msg,msg))
        else:
            raise RuntimeError("thread is not running")
    def start(self, period, sync=True):
        if self.running:
            raise RuntimeError("thread is already running")
        threading.Thread(target=self.loop,args=(period,sync)).start()
        if sync:
            ack_msg=self.ack_queue.get()
            if ack_msg!="start":
                raise RuntimeError("wrong acknowledgment '{0}' for message 'start'".format(ack_msg))
    def stop(self, sync=True):
        self.send_message("stop",sync=sync)
    def pause(self, sync=True):
        self.send_message("pause",sync=sync)
    def resume(self, sync=True):
        self.send_message("resume",sync=sync)
    
    def is_looping(self):
        return self.running and not self.paused
    def is_running(self):
        return self.running