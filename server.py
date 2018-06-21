# -*- coding: utf-8 -*-

import time
import hprose
import threading

default_config = {
    "rpc_server": "http://127.0.0.1:8181/",
    "port": 8282
}

RESET_TYPE = {
    0: "user passwd",
    1: "user data"
}

# notice codes from master process
MATER_READY_FOR_UPDATE = 0
MASTER_PROCESS_STARTED = 0
UPDATE_READY_FOR_DOWNLOAD = 1
DISCOVER_MODE_ACTIVATED = 2
MASTER_PROCESS_ERROR = 3

# nocice codes to master process
UPDATE_PACKAGE_DOWNLOADED = 1
INSUFFICIENT_MEMORY = 2
INSUFFICIENT_SPACE = 3

class Simulator:
    def __init__(self, config=None):
        config = config or {}
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

        print("[  SI-INFO  ] Simulator initialized .")

    def start(self):
        self.start_simulating()
        try:
            self.server.start()
        except KeyboardInterrupt:
            self.simulator_stop = True
            time.sleep(1)
            print("[  SI-INFO  ] Simulator stopped by user .")

    def start_simulating(self):
        threading.Thread(target=self._start_simulating, args=()).start()

    def _start_simulating(self):
        print("[  SI-INFO  ] <SIMULATING> MASTER STARTING ...")
        time.sleep(5)
        self.client.notice(MASTER_PROCESS_STARTED, detail={})
        print("[  SI-INFO  ] <SIMULATING> MASTER STARTED .")

    def ping(self):
        print("[  SI-INFO  ] Simulator received a `ping` .")
        return "pong"

    def notice(self, code, detail=None):
        detail = detail or {}
        if code == UPDATE_PACKAGE_DOWNLOADED:
            print("[  SI-INFO  ] Simulator received a notice: update package downloaded .")
            time.sleep(2)  # simulating the costing time before getting ready
            return MATER_READY_FOR_UPDATE
        if code == INSUFFICIENT_MEMORY:
            print("[  SI-INFO  ] Simulator received a notice: insufficient memory .")
        if code == INSUFFICIENT_SPACE:
            print("[  SI-INFO  ] Simulator received a notice: insufficient space .")
            
    def restart(self):
        print("[  SI-INFO  ] Simulator restarted .")
            
    def discover(self):
        print("[  SI-INFO  ] Simulator in discover mode .")
            
    def reset(self, type=-1):
        print("[  SI-INFO  ] Simulator reset: %s" % RESET_TYPE.get(type, "unknown"))

    def onGPIO(self, pin, type, value):
        print("[  SI-INFO  ] Simulator GPIO event .")
