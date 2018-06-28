# -*- coding: utf-8 -*-

import os
import sys
import time
import json
import hprose
import threading

# default_config = {
#     "rpc_server": "http://127.0.0.1:8181/",
#     "port": 8282,
#     "logfile": "./simu_server_log"
# }

default_config = {
    "rpc_server": "tcp://127.0.0.1:7000/",
    "port": 7001,
    "logfile": "./simu_server_log"
}

UPDATE_PKG_URL = "https://github.com/catcuts/isht/raw/updatepkg/vigserver.zip"

RESET_TYPE = {
    0: "user passwd",
    1: "user data"
}

# notice codes from master process
MASTER_READY_FOR_UPDATE = 0
MASTER_RESTARTED = True
MASTER_RESETTED = True

MASTER_PROCESS_STARTED = 0
UPDATE_READY_FOR_DOWNLOAD = 1
DISCOVER_MODE_ACTIVATED = 2
DISCOVER_MODE_DEACTIVATED = 3
MASTER_PROCESS_ERROR = 4

# nocice codes to master process
UPDATE_PACKAGE_DOWNLOADED = 1
INSUFFICIENT_MEMORY = 2
INSUFFICIENT_SPACE = 3

class Simulator:
    def __init__(self, config=None):
        self.config = config or {}
        [config.setdefault(k, v) for k, v in default_config.items()]

        self.rpc_server = uri = config.get("rpc_server")
        self.client = hprose.HttpClient(uri)

        self.port = port = config.get("port")
        self.server = server = hprose.HttpServer(port=port)
        server.addFunctions([
            self.ping,
            self.notice,
            self.restart,
            self.discover,
            self.reset,
            self.onGPIO,
            self.progress
        ])

        self.simulator_stop = False
        self.pid = None

        self.logfile = config.get("logfile")
        with open(self.logfile, "w") as f:
            print("", file=f)

        self.printl("[  SI-INFO  ] Simulator initialized : \n%s" % json.dumps(self.config, indent=4))

    def start(self):
        self.start_simulating()
        try:
            self.pid = os.getpid()
            self.server.start()
        except KeyboardInterrupt:
            self.simulator_stop = True
            time.sleep(1)
            self.printl("[  SI-INFO  ] Simulator stopped by user .")
        except Exception as E:
            self.printl("[  MO-ERROR  ] Local rpc server failed to start : %s" % E)

    def start_simulating(self):
        threading.Thread(target=self._start_simulating, args=()).start()

    def _start_simulating(self):
        self.printl("[  SI-INFO  ] <SIMULATING> MASTER STARTING ...")
        time.sleep(2)
        self.printl("[  SI-INFO  ] <SIMULATING> MASTER STARTED .")

        if self.try_notify(args=(MASTER_PROCESS_STARTED, {})):
            self.printl("[  SI-INFO  ] SUCCESSFULLY NOTIFIED .")
        else:
            self.printl("[  SI-INFO  ] FAILED TO NOTIFIED .")

        self.printl("[  SI-INFO  ] <SIMULATING> MASTER NEED UPDATING ...")
        time.sleep(2)
        self.printl("[  SI-INFO  ] <SIMULATING> MASTER UPDATE PACKAGE READY FOR DOWNLOAD .")
        
        if self.try_notify(args=(UPDATE_READY_FOR_DOWNLOAD, {
            "url": UPDATE_PKG_URL
        })):
            self.printl("[  SI-INFO  ] SUCCESSFULLY NOTIFIED .")
        else:
            self.printl("[  SI-INFO  ] FAILED TO NOTIFIED .")

    def try_notify(self, number_of_try=0, interval=1, args=()):
        try:
            self.client.notice(*args)
            return True
        except ConnectionRefusedError:
            remain_times = ("REMIANED %s" % number_of_try) if number_of_try else ""
            self.printl("[  SI-INFO  ] <SIMULATING> CONNECTION REFUSED . TRYING ... %s" % remain_times)
            if interval > 0: time.sleep(interval)
            if number_of_try <= 0:
                return self.try_notify(0, interval, args)
            else:
                return self.try_notify(number_of_try - 1, interval, args)     
    
    # @RPC
    def ping(self):
        self.printl("[  SI-INFO  ] Simulator received a `ping` .")
        return self.pid
    
    # @RPC
    def notice(self, code, detail=None):
        detail = detail or {}
        if code == UPDATE_PACKAGE_DOWNLOADED:
            self.printl("[  SI-INFO  ] Simulator received a notice: update package downloaded .")
            time.sleep(2)  # simulating the costing time before getting ready
            return MASTER_READY_FOR_UPDATE
        if code == INSUFFICIENT_MEMORY:
            return self.printl("[  SI-INFO  ] Simulator received a notice: insufficient memory .")
        if code == INSUFFICIENT_SPACE:
            return self.printl("[  SI-INFO  ] Simulator received a notice: insufficient space .")
    
    # @RPC            
    def restart(self):
        self.printl("[  SI-INFO  ] Simulator restarted .")
        return MASTER_RESTARTED
    
    # @RPC            
    def discover(self):
        self.printl("[  SI-INFO  ] Simulator in discover mode .")

        def disable_discover():
            time.sleep(5)
            self.printl("[  SI-INFO  ] Simulator quit discover mode .")
            self.notice(DISCOVER_MODE_DEACTIVATED, detail={})

        threading.Thread(target=disable_discover).start()

        return DISCOVER_MODE_ACTIVATED
    
    # @RPC            
    def reset(self, type=-1):
        self.printl("[  SI-INFO  ] Simulator reset: %s" % RESET_TYPE.get(type, "unknown"))
        return MASTER_RESETTED

    # @RPC
    def onGPIO(self, pin, type, value):
        return self.printl("[  SI-INFO  ] Simulator GPIO event .")

    # @RPC
    def progress(self, progress, message, code):
        status = "Normal" if code else "Abnormal"
        return self.printl("[  SI-INFO  ] Progress from Assistant: %s %s (status: %s)" % (progress, message, status))

    # @LOCAL
    def printl(self, logline, screen=False):   
        logtime = time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(time.time()))
        logline = "[%s]%s" % (logtime, logline) 
        with open(self.logfile, "a") as f:
            print(logline, file=f)
            if screen: print(logline)

if __name__ == '__main__':

    Simulator(default_config).start()