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
    "rpc_server": "http://127.0.0.1:8282/",
    "port": 8181,
    "gpio_inputs": {
        "set": "PA10",
        "reset": "PA9"
    },
    "gpio_outputs": {
        "led": "STATUS_LED"
    },
    "download_dir": "/tmp/download"
}

USERPASSWD = 0
USERDATA = 1

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

# led blink pattern
ALWAYS_ON = (0, 0)
LONG_BLINK = (0.2, 1.2)
SHORT_BLINK = (0.2, 0.2)
HIGH_FREQ_BLINK = (0.05, 0.05)

class Monitor:
    def __init__(self, config=None):
        config = config or {}
        [config.setdefault(k, v) for k, v in default_config.items()]
        
        self.rpc_server = uri = config.get("rpc_server")
        self.client = hprose.HttpClient(uri)

        self.port = port = config.get("port")
        self.server = server = hprose.HttpServer(port=port)
        server.addFunctions([
            self.notice,
            self.readGPIO,
            self.listenGPIO,
            self.cancelListenGPIO,
            self.writeGPIO
        ])

        self.gpio = {}
        self.led_stop = False
        self.led_current_blink = ()
        self.monitor_stop = False

        print("[  MO-INFO  ] Monitor initialized .")

    def start(self):
        threading.Thread(target=self.server.start, args=()).start()
        try:
            self.init_gpio_monitoring()
            self.start_gpio_monitoring()
            self.blink_led(*LONG_BLINK)
            # self.start_env_monitoring()
            # self.start_local_rpc_server()
            self.ping()
        except KeyboardInterrupt:
            self.led_stop = True
            self.monitor_stop = True
            time.sleep(0.1)
            print("[  MO-INFO  ] Monitor stopped by user .")

    def start_env_monitoring(self):
        threading.Thread(target=self._start_env_monitoring, args=()).start()

    def _start_env_monitoring(self):
        while not self.monitor_stop:
            print("[  MO-INFO  ] <FAKE> ENV MONITORING ...")
            time.sleep(1)
        print("[  MO-INFO  ] ENV MONITORING STOPPED .")

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
            self.blink_led(*ALWAYS_ON)
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

        enable_reset = (gpio.input(reset_button) == gpio.HIGH)
        reset_noted = False
        time_start_reset = 0
        time_kept_reset = 0
        time_kept_reset_last = 0

        enable_set = (gpio.input(set_button) == gpio.HIGH)
        set_noted = False
        time_start_set = 0
        time_kept_set = 0
        time_kept_set_last = 0
        
        while not self.monitor_stop:
            reset_count = 1
            set_count = 1
            led_blink_last = ()

            if enable_reset and enable_set:  # 两个键都没按下的时候方可使能，即都为高电平
                if not gpio.input(reset_button) or not gpio.input(set_button):  # 有一个键按下，则检测到低电平，则为下降沿
                    led_blink_last = self.led_current_blink  # 保存当前 led 闪烁方式以备恢复
                    self.blink_led(*HIGH_FREQ_BLINK)  # 高频闪烁以提示
                    reset_value = gpio.input(reset_button)
                    set_value = gpio.input(set_button)
                    while not reset_value or not set_value:  # 循环等待两个键都放开，即都为高电平
                        
                        reset_value = gpio.input(reset_button)
                        set_value = gpio.input(set_button)

                        reset_button_is_up = reset_noted and reset_value
                        set_button_is_up = set_noted and set_value 
                        
                        # 对于 reset 键
                        if not reset_value:
                            if time_kept_reset > reset_count:  # 提示
                                print("[  MO-DEBUG  ] Reset button pressed for: %s" % time_kept_reset)
                                reset_count += 1

                            if not reset_noted:  # 还未记下开始时间
                                time_start_reset = time.time()  # 记下开始时间
                                reset_noted = True  # 不要重复记录开始时间
                            else:  # 已经记录过开始时间，则计算时长
                                time_kept_reset = time.time() - time_start_reset

                        # 放开时复位（前提是 set 键没放开）
                        elif set_button_is_up:  
                            reset_noted = False
                            time_kept_reset_last = time_kept_reset
                            time_kept_reset = 0
                            reset_count = 1
                        
                        # 对于 set 键
                        if not set_value:
                            if time_kept_set > set_count:  # 提示
                                print("[  MO-DEBUG  ] Set button pressed for: %s" % time_kept_set)
                                set_count += 1

                            if not set_noted:  # 第一次进入低电平
                                time_start_set = time.time()  # 记下开始时间
                                set_noted = True  # 不要重复记录开始时间
                            else:  # 已经记录过开始时间，则计算时长
                                time_kept_set = time.time() - time_start_set

                        # 放开时复位（前提是 reset 键没放开）
                        elif reset_button_is_up:  
                            set_noted = False
                            time_kept_set_last = time_kept_set
                            time_kept_set = 0
                            set_count = 1

                    # 两个键都已放开
                    
                    # 两个键都被按下为最优先（此时前面的 time_kept 没用）
                    if time_kept_reset_last and time_kept_set_last:
                        time_start_first_btn = min(time_start_reset, time_kept_set_last)
                        time_start_second_btn = max(time_start_reset, time_kept_set_last)

                        time_kept_first_btn = time.time() - time_start_first_btn
                        delta_time_start = abs(time_start_first_btn - time_start_second_btn)
                        
                        time_kept_two_btns = time_kept_first_btn - delta_time_start
                        print("[  MO-DEBUG  ] Reset with Set button pressed for %s secs" % time_kept_two_btns)
                        if time_kept_two_btns >= 3:
                            print("[  MO-INFO  ] Recovery is going to be activated !") 
                            self.blink_led(*SHORT_BLINK)
                            self.recover()

                    # 然后是 reset 键
                    elif time_kept_reset >= 5 and time_kept_reset < 10:
                        print("[  MO-INFO  ] Passwd is going to be reset !")
                        self.blink_led(*LONG_BLINK)
                        self.reset(USERPASSWD)
                        print("[  MO-INFO  ] Passwd reset !")
                    
                    elif time_kept_reset >= 10:
                        print("[  MO-INFO  ] Userdata is going to be reset !")
                        self.blink_led(*SHORT_BLINK)
                        self.reset(USERDATA)
                        print("[  MO-INFO  ] Userdata reset !")

                    # 最后是 set 键
                    elif time_kept_set > 0 and time_kept_set < 3:
                        print("[  MO-INFO  ] Restart is going to be activated !")
                        self.blink_led(*LONG_BLINK)
                        self.restart()
                        print("[  MO-INFO  ] Restart activated !")
                    
                    elif time_kept_set >= 3:
                        print("[  MO-INFO  ] Discover mode is going to be activated !")
                        self.blink_led(*LONG_BLINK)
                        self.discover()
                        print("[  MO-INFO  ] Discover mode activated !")
            
            enable_reset = (gpio.input(reset_button) == gpio.HIGH)
            reset_noted = False
            time_start_reset = 0
            time_kept_reset = 0
            time_kept_reset_last = 0

            enable_set = (gpio.input(set_button) == gpio.HIGH)
            set_noted = False
            time_start_set = 0
            time_kept_set = 0
            time_kept_set_last = 0

            if led_blink_last:  # 恢复 led 上一次的闪烁方式
                self.blink_led(led_blink_last)
                led_blink_last = ()

            continue
            
            # bkup code
            
            if enable_reset:
                if gpio.input(reset_button) == gpio.LOW:  # 如果检测到低电平，即为下升沿
                    while gpio.input(reset_button) == gpio.LOW:  # 循环等待高电平
                        # time.sleep(0.01)
                        if time_kept_reset > count:
                            print("[  MO-INFO  ] Reset button pressed for: %s" % time_kept_reset)
                            count += 1
                        if not reset_noted:  # 第一次进入低电平
                            reset_noted = True  # 则下次不要进来了
                            time_start_reset = time.time()  # 记下开始时间
                        time_kept_reset = time.time() - time_start_reset  # 长按时长

                    if time_kept_reset >= 5 and time_kept_reset < 10:
                        print("[  MO-INFO  ] Passwd is going to be reset !")
                        self.blink_led(*LONG_BLINK)
                        self.reset(USERPASSWD)
                        print("[  MO-INFO  ] Passwd reset !")
                    
                    elif time_kept_reset >= 10:
                        print("[  MO-INFO  ] Userdata is going to be reset !")
                        self.blink_led(*SHORT_BLINK)
                        self.reset(USERDATA)
                        print("[  MO-INFO  ] Userdata reset !")

                    reset_noted = False
                    time_kept_reset = 0
                    count = 1

            elif enable_set:
                if gpio.input(set_button) == gpio.LOW:  # 如果检测到低电平，即为下升沿
                    while gpio.input(set_button) == gpio.LOW:  # 循环等待高电平
                        # time.sleep(0.01)
                        if time_kept_set > count:
                            print("[  MO-INFO  ] Set button pressed for: %s" % time_kept_set)
                            count += 1
                        if not set_noted:  # 第一次进入低电平
                            set_noted = True  # 则下次不要进来了
                            time_start_set = time.time()  # 记下开始时间
                        time_kept_set = time.time() - time_start_set  # 长按时长

                    if time_kept_set < 3:
                        print("[  MO-INFO  ] Restart is going to be activated !")
                        self.blink_led(*LONG_BLINK)
                        self.restart()
                        print("[  MO-INFO  ] Restart activated !")
                    
                    elif time_kept_set >= 3:
                        print("[  MO-INFO  ] Discover mode is going to be activated !")
                        self.blink_led(*LONG_BLINK)
                        self.discover()
                        print("[  MO-INFO  ] Discover mode activated !")

                    set_noted = False
                    time_kept_set = 0
                    count = 1

    def dark_led(self):
        self.led_stop = True
        time.sleep(0.1)
        self.led_stop = False
        gpio.output(self.gpio.get("led"), gpio.LOW)
        self.led_current_blink = ()

    def blink_led(self, interval_dark=0, interval_light=0):
        self.dark_led()

        value = gpio.HIGH
        gpio.output(self.gpio.get("led"), value)
        
        if interval_dark and interval_light:
            threading.Thread(target=self._blink_led, args=(interval_dark, interval_light)).start()

        self.led_current_blink = (interval_dark, interval_light)

    def _blink_led(self, interval_dark=0, interval_light=0):
        zerone = cycle((gpio.LOW, gpio.HIGH))
        value = gpio.HIGH
        while not self.led_stop:
            if value:
                time.sleep(interval_light)
            else:
                time.sleep(interval_dark)
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

    # def ping(self):
    #     threading.Thread(target=self._ping, args=()).start()

    def ping(self):
        while not self.monitor_stop:
            pong = print("[  MO-INFO  ] <FAKE> PING ...")
            # if not pong:
            #     self.kill()
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

    def recover(self):
        print("[  MO-INFO  ] <FAKE> RECOVERY ACTIVATED .")

if __name__ == '__main__':
    try:
        uri = sys.argv[1]
    except:
        uri = "http://127.0.0.1:8181/"

    config = copy(default_config)
    config["rpc_server"] = uri
    Monitor(config).start()