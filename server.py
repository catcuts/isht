# -*- coding: utf-8 -*-

import sys
import time
import json
import hprose
import threading
from copy import copy

default_config = {
    "rpc_server": "http://127.0.0.1:8181/",
    "port": 8282
}

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
        self.config = config = config or {}
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
            self.onGPIO
        ])

        self.simulator_stop = False

        print("[  SI-INFO  ] Simulator initialized : \n%s" % json.dumps(self.config, indent=4))

    def start(self):
        self.start_simulating()
        try:
            self.server.start()
        except KeyboardInterrupt:
            self.simulator_stop = True
            time.sleep(1)
            print("[  SI-INFO  ] Simulator stopped by user .")
        except Exception as E:
            print("[  MO-ERROR  ] Local rpc server failed to start : %s" % E)

    def start_simulating(self):
        threading.Thread(target=self._start_simulating, args=()).start()

    def _start_simulating(self):
        print("[  SI-INFO  ] <SIMULATING> MASTER STARTING ...")
        time.sleep(2)
        print("[  SI-INFO  ] <SIMULATING> MASTER STARTED .")

        if self.try_notify(args=(MASTER_PROCESS_STARTED, {})):
            print("[  SI-INFO  ] SUCCESSFULLY NOTIFIED .")
        else:
            print("[  SI-INFO  ] FAILED TO NOTIFIED .")

        print("[  SI-INFO  ] <SIMULATING> MASTER NEED UPDATING ...")
        time.sleep(2)
        print("[  SI-INFO  ] <SIMULATING> MASTER UPDATE PACKAGE READY FOR DOWNLOAD .")
        
        if self.try_notify(args=(UPDATE_READY_FOR_DOWNLOAD, {})):
            print("[  SI-INFO  ] SUCCESSFULLY NOTIFIED .")
        else:
            print("[  SI-INFO  ] FAILED TO NOTIFIED .")

    def try_notify(self, number_of_try=0, interval=1, args=()):
        try:
            self.client.notice(*args)
            return True
        except ConnectionRefusedError:
            remain_times = ("REMIANED %s" % number_of_try) if number_of_try else ""
            print("[  SI-INFO  ] <SIMULATING> CONNECTION REFUSED . TRYING ... %s" % remain_times)
            if interval > 0: time.sleep(interval)
            if number_of_try <= 0:
                return self.try_notify(0, interval, args)
            else:
                return self.try_notify(number_of_try - 1, interval, args)     
    
    # @RPC
    def ping(self):
        print("[  SI-INFO  ] Simulator received a `ping` .")
        return "pong"
    
    # @RPC
    def notice(self, code, detail=None):
        detail = detail or {}
        if code == UPDATE_PACKAGE_DOWNLOADED:
            print("[  SI-INFO  ] Simulator received a notice: update package downloaded .")
            time.sleep(2)  # simulating the costing time before getting ready
            return MASTER_READY_FOR_UPDATE
        if code == INSUFFICIENT_MEMORY:
            print("[  SI-INFO  ] Simulator received a notice: insufficient memory .")
        if code == INSUFFICIENT_SPACE:
            print("[  SI-INFO  ] Simulator received a notice: insufficient space .")
    
    # @RPC            
    def restart(self):
        print("[  SI-INFO  ] Simulator restarted .")
        return MASTER_RESTARTED
    
    # @RPC            
    def discover(self):
        print("[  SI-INFO  ] Simulator in discover mode .")

        def disable_discover():
            time.sleep(5)
            print("[  SI-INFO  ] Simulator quit discover mode .")
            self.notice(DISCOVER_MODE_DEACTIVATED, detail={})

        threading.Thread(target=disable_discover).start()

        return DISCOVER_MODE_ACTIVATED
    
    # @RPC            
    def reset(self, type=-1):
        print("[  SI-INFO  ] Simulator reset: %s" % RESET_TYPE.get(type, "unknown"))
        return MASTER_RESETTED

    # @RPC
    def onGPIO(self, pin, type, value):
        print("[  SI-INFO  ] Simulator GPIO event .")

    # @RPC
    def progress(self, progress, message, code):
        status = "Normal" if code else "Abnormal"
        print("[  SI-INFO  ] From Assistant: %s %s (status: %s)" % (progress, message, status))

if __name__ == '__main__':

    config = copy(default_config)

    try:
        uri = sys.argv[1]
    except:
        uri = "http://127.0.0.1:8181/"

    try:
        local_rpc_port = sys.argv[2]
    except:
        local_rpc_port = 8282

    config["rpc_server"] = uri
    config["port"] = local_rpc_port

    Simulator(config).start()