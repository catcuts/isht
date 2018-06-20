# -*- coding: utf-8 -*-

import sys
import time
import hprose
import threading
from copy import copy
from itertools import cycle
from pyA20.gpio import gpio
from pyA20.gpio import port
from pyA20.gpio import connector

default_config = {
    "rpc_server": "http://127.0.0.1:8181/",
    "gpio_inputs": {
        "set": "PA10",
        "reset": "PA9"
    },
    "gpio_outputs": {
        "led": "PG6"
    },
    "download_dir": "/tmp/download"
}

USERPASSWD = 0
USERDATA = 1

# notice codes from master process
MASTER_PROCESS_STARTED = 0,
UPDATE_READY_FOR_DOWNLOAD = 1
DISCOVER_MODE_ACTIVATED = 2
MASTER_PROCESS_ERROR = 3

# nocice codes to master process
UPDATE_PACKAGE_DOWNLOADED = 1
INSUFFICIENT_MEMORY = 2
INSUFFICIENT_SPACE = 3

class Monitor:
    def __init__(self, config=None):
        config = config or {}
        [config.setdefault(k, v) for k, v in default_config.items()]
        self.rpc_server = uri = config.get("rpc_server")
        self.client = hprose.HttpClient(uri)
        self.gpio = {}
        self.led_stop = False
        self.monitor_stop = False
        print("[  MO-INFO  ] Monitor initialized.")

    def start(self):
        try:
            self.init_gpio_monitoring()
            self.start_gpio_monitoring()
            self.blink_led(interval=1.2)
            self.start_env_monitoring()
            self.start_local_rpc_server()
            self.ping()
        except KeyboardInterrupt:
            self.led_stop = True
            self.monitor_stop = True
            time.sleep(1)
            print("[  MO-INFO  ] Monitor stopped by user .")

    def start_env_monitoring(self):
        threading.Thread(target=self._start_env_monitoring, args=()).start()

    def _start_env_monitoring(self):
        while not self.monitor_stop:
            print("[  MO-INFO  ] <FAKE> ENV MONITORING ...")
            time.sleep(1)
        print("[  MO-INFO  ] ENV MONITORING STOPPED ...")

    def start_local_rpc_server(self):
        threading.Thread(target=self._start_local_rpc_server, args=()).start()

    def _start_local_rpc_server(self):
        while not self.monitor_stop:
            print("[  MO-INFO  ] <FAKE> LOCAL RPC SERVER RUNNING ...")
            time.sleep(1)
        print("[  MO-INFO  ] LOCAL RPC SERVER STOPPED .")

    def notice(self, code=-1, detail=None):
        if code == MASTER_PROCESS_STARTED:
            print("[  MO-INFO  ] Master process is stared .")
            self.blink_led(interval=0)
        elif code == UPDATE_READY_FOR_DOWNLOAD:
            print("[  MO-INFO  ] Downloading update package ...")
            self.download()
        elif code == DISCOVER_MODE_ACTIVATED:
            print("[  MO-INFO  ] Discover mode activated .")
            # do some thing that to be determined
        elif code == MASTER_PROCESS_ERROR:
            print("[  MO-INFO  ] Mater process error .")
            # do some thing that to be determined like show detail errors

    def readGPIO(self, pin):
        return "to be done"

    def listenGPIO(self, pin, type):
        return "to be done"

    def cancelListenGPIO(self, pin, type):
        return "to be done"

    def writeGPIO(pin, value):
        return "to be done"

    def init_gpio_monitoring(self):
        # Init gpio module
        gpio.init()
        print("[  MO-INFO  ] GPIO initialized.")

        # Set directions
        gpio_inputs = config.get("gpio_inputs", {})
        gpio_outputs = config.get("gpio_outputs", {})

        for func_name, pin_name in gpio_inputs.items():
            if pin_name.startswith("gpio"):
                self.gpio[func_name] = _gpio_input = getattr(connector, pin_name)
            else:
                self.gpio[func_name] = _gpio_input = getattr(port, pin_name)
            gpio.setcfg(_gpio_input, gpio.INPUT)

        for func_name, pin_name in gpio_outputs.items():
            if pin_name.startswith("gpio"):
                self.gpio[func_name] = _gpio_output = getattr(connector, pin_name)
            else:
                self.gpio[func_name] = _gpio_output = getattr(port, pin_name)
            gpio.setcfg(_gpio_output, gpio.OUTPUT)
        print("[  MO-INFO  ] GPIO configured:"
            "\n\tgpio_inputs:"
            "\n\t\t%s"
            "\n\tgpio_outputs:"
            "\n\t\t%s" % ("emitting", "emitting"))

    def start_gpio_monitoring(self):
        threading.Thread(target=self._start_gpio_monitoring, args=()).start()

    def _start_gpio_monitoring(self):
        reset_button = self.gpio.get("reset")
        set_button = self.gpio.get("set")
        led = self.gpio.get("led")

        enable_reset = (gpio.input(reset_button) == gpio.LOW)
        first_high_reset = False
        time_start_reset = 0
        time_kept_reset = 0

        enable_set = (gpio.input(set_button) == gpio.LOW)
        first_high_set = False
        time_start_set = 0
        time_kept_set = 0
        
        while not self.monitor_stop:  # reset 优先级更高
            reset_value = gpio.input(reset_button)
            set_value = gpio.input(set_button)
            if enable_reset:
                if reset_value == gpio.HIGH:  # 如果检测到高电平，即为上升沿
                    while gpio.input(reset_button) == gpio.HIGH:  # 循环等待低电平
                        time.sleep(0.01)
                        if not first_high_reset:  # 第一次进入高电平
                            first_high_reset = True  # 则下次不要进来了
                            time_start_reset = time.time()  # 记下开始时间
                        time_kept_reset = time.time() - time_start_reset  # 长按时长

                    if time_kept_reset >= 5:
                        print("[  MO-INFO  ] Passwd is going to be reset !")
                        self.blink_led(interval=1.2)
                        self.reset(USERPASSWD)
                        print("[  MO-INFO  ] Passwd reset !")
                    
                    elif time_kept_reset >= 10:
                        print("[  MO-INFO  ] Userdata is going to be reset !")
                        self.blink_led(interval=0.1)
                        self.reset(USERDATA)
                        print("[  MO-INFO  ] Userdata reset !")

            elif enable_set:
                if set_value == gpio.HIGH:  # 如果检测到高电平，即为上升沿
                    while gpio.input(set_button) == gpio.HIGH:  # 循环等待低电平
                        time.sleep(0.01)
                        if not first_high_set:  # 第一次进入高电平
                            first_high_set = True  # 则下次不要进来了
                            time_start_set = time.time()  # 记下开始时间
                        time_kept_set = time.time() - time_start_set  # 长按时长

                    if time_kept_set < 3:
                        print("[  MO-INFO  ] Restart is going to be activated !")
                        self.blink_led(interval=1.2)
                        self.restart()
                        print("[  MO-INFO  ] Restart activated !")
                    
                    elif time_kept_set > 10:
                        print("[  MO-INFO  ] Discover mode is going to be activated !")
                        self.blink_led(interval=1.2)
                        self.discover()
                        print("[  MO-INFO  ] Discover mode activated !")

            enable_reset = (reset_value == gpio.LOW)
            enable_set = (set_value == gpio.LOW)

    def dark_led(self):
        self.led_stop = True
        time.sleep(0.1)
        gpio.output(self.gpio.get("led"), gpio.LOW)

    def blink_led(self, interval=0):
        self.dark_led()
        
        value = gpio.HIGH
        gpio.output(self.gpio.get("led"), value)
        
        if interval:
            zerone = cycle((gpio.LOW, gpio.HIGH))
            threading.Thread(target=self._blink_led, args=()).start()

    def _blink_led(self, interval=0):
        zerone = cycle((gpio.LOW, gpio.HIGH))
        while not self.led_stop:
            time.sleep(interval)
            value = next(zerone)
            gpio.output(self.gpio.get("led"), value)

    def reset(self, type):
        print("[  MO-INFO  ] <FAKE> CALLING RPC.RESET FUNCTION .")
        time.sleep(1)

    def restart(self):
        print("[  MO-INFO  ] <FAKE> CALLING RPC.RESTART FUNCTION .")
        time.sleep(1)

    def discover(self):
        print("[  MO-INFO  ] <FAKE> CALLING RPC.DISCOVER FUNCTION .")
        time.sleep(1)

    def ping(self):
        while not self.monitor_stop:
            pong = print("[  MO-INFO  ] <FAKE> PING ...")
            if not pong:
                self.kill()
            time.sleep(20)
        pong = print("[  MO-INFO  ] PING STOPPED .")

    def kill(self):
        print("[  MO-INFO  ] <FAKE> KILLING MASTER .")

    def notify(self, code=-1, detail=None):
        detail = detail or {}
        print("[  MO-INFO  ] <FAKE> CALLING RPC.NOTICE FUNCTION .")

    def on_gpio(self, pin, type, value):
        print("[  MO-INFO  ] <FAKE> CALLING RPC.ONGPIO FUNCTION .")
    
    def download(self, url="", dest=None):
        dest = dest or self.config.get("download_dir")
        print("[  MO-INFO  ] <FAKE> DOWNLOADING FROM %s ..." % url)
        time.sleep(5)
        print("[  MO-INFO  ] <FAKE> DOWNLOADED FROM %s AND TO %s." % (url, dest))
        self.notify(UPDATE_PACKAGE_DOWNLOADED, detail={})

if __name__ == '__main__':
    try:
        uri = sys.argv[1]
    except:
        uri = "http://127.0.0.1:8181/"

    config = copy(default_config)
    config["rpc_server"] = uri
    Monitor(config).start()