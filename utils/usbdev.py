# -*- coding: utf-8 -*-

import re
import time
import threading
import subprocess

CMD_LIST_SDX = "ls /dev/sd*"

class MassStorageUSBListerner:
    """
    this is a temporate class
    which future will be a sub class
    to a USBListerner class
    """

    def __init__(self, filter_=None, callback=None, interval=0, logfile=None):
        """
        callback eg= {
            "on_plug_in": lambda dev: print("on plug in"),
            "on_plug_out": lambda dev: print("on plug out"),             
        }
        """
        self.filter = filter_
        self.callback = callback or {}
        self.amount = 0
        self.devices = []
        self.status = "init"
        self.interval = interval
        self.logfile = logfile

    def start(self, callback=None):
        self.callback = callback or self.callback
        if self.status == "start":
            self.log("[  UL-WARN  ] Starting refused, already listening .")
        else:
            self.status = "start"
            self.log("[  UL-INFO  ] Listerning started .")
            self.listrening()

    def stop(self):
        self.status = "stop"
        time.sleep(0.1)

    def listrening(self):
        try:
            while self.status != "stop":
                # self.log("meow ...")
                self.find()
                if self.interval: time.sleep(self.interval)
                self.log("meow ...")
        except KeyboardInterrupt:
            pass
        self.log("[  UL-INFO  ] Listerning stopped .")

    def find(self):
        pipe = subprocess.Popen(CMD_LIST_SDX, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        err = pipe.stderr.read()
        if err:
            # self.log("[  UL-ERROR  ] Error executing `%s`: %s" % (CMD_LIST_SDX, err))
            devices = []
        else:
            devs = pipe.stdout.read().decode().strip('\n').split('\n')
            devices = [dev for dev in devs if re.sub("\d+$", "", dev) in devs]
            
        amount = len(devices)

        if amount == self.amount: return False

        if amount < self.amount:
            old_devices = list(set(self.devices) - set(devices))
            [self.devices.pop(self.devices.index(dev)) for dev in old_devices]  # self.devices contains old_devices so no index error will happen
            self.on_plug_out(old_devices)
        elif amount > self.amount:
            new_devices = list(set(devices) - set(self.devices))
            [self.devices.append(dev) for dev in new_devices]
            self.on_plug_in(new_devices)

        self.amount = amount
        return True

    def on_plug_in(self, devices):
        self.log("[  UL-INFO  ] Something plugged in .")
        callback = self.callback.get("on_plug_in")
        if callable(callback): 
            for device in devices:
                try:
                    threading.Thread(target=callback, args=(device,)).start()
                except Exception as E:
                    self.log("[  UL-ERROR  ] Error while callback on <%s> plug in: \n\t%s" % (device, E))

    def on_plug_out(self, devices):
        self.log("[  UL-INFO  ] Something plugged out .")
        callback = self.callback.get("on_plug_out")
        if callable(callback): 
            for device in devices:
                try:
                    threading.Thread(target=callback, args=(device,)).start()
                except Exception as E:
                    self.log("[  UL-ERROR  ] Error while callback on <%s> plug out: \n\t%s" % (device, E))

    def log(self, logline, screen=True):
        logtime = time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(time.time()))
        logline = "[%s]%s" % (logtime, logline) 
        if self.logfile:
            with open(self.logfile, "a") as f:
                print(logline, file=f)
        if screen or not self.logfile: print(logline)

if __name__ == "__main__":

    listerner = MassStorageUSBListerner()
    listerner.start()