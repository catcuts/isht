# -*- coding: utf-8 -*-

import os
import sys

root_path = os.path.abspath(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, root_path)

import time
import json
import hprose
import requests
import threading
from utils.update import UpdateManager
from utils.md5hash import md5_from_file, md5_from_string
from utils.usbdev import MassStorageUSBListerner
from utils.shellcmder import ShellCommander
from itertools import cycle
from pyA20.gpio import gpio
from pyA20.gpio import port
from pyA20.gpio import connector
import atexit
import traceback

default_config = {
    # RPC
    "rpc_server": "http://127.0.0.1:8282/",
    "host": "127.0.0.1",
    "port": 8181,
    
    # GPIO
    "gpio_inputs": {
        "set": "PA10",
        "reset": "PA9"
    },
    "gpio_outputs": {
        "led": "STATUS_LED"
    },
    
    # FILES AND FOLDERS
    "master_dir": "/usr/local/hyt/vigserver",
    "download_dir": "/usr/local/hyt/download",
    "mount_dir": "/usr/local/hyt/mount",
    "backup_dir": "/usr/local/hyt/backup",
    "backup_excludes": [
        "/usr/local/hyt/vigserver/node_modules"
    ],
    "update_pkg_name": "vigserver_firmware.zip",
    "bakcup_pkg_name": "vigserver_bkup_latest.zip",

    # MD5 VERIFICATION SPECIFIED FILES
    "verifying_files": [
        "server.js",
        "core/device/manager.js",
        "core/eventbus/eventbus.js"
    ],

    # COMMAND
    # "start_cmd": "sudo python3.6 ./server.py",
    "start_cmd": "sudo node --inspect=0.0.0.0 /usr/local/hyt/vigserver/start.js > /dev/null",
    "kill_cmd": "ps aux | grep /usr/local/hyt/vigserver/start.js | awk '{print $2}' | xargs kill -9",

    # DBUG
    "debug": True,

    # LOG
    "logfile": "/usr/local/hyt/vigmonitor/log",

    # PICKLE
    "picklefile": "/usr/local/hyt/vigmonitor/pickle",

    # ENVIRON
    "environ": "environ"
}

USERPASSWD = 0
USERDATA = 1

# notice codes from master process
# MASTER_READY_FOR_UPDATE = 0
MASTER_READY_FOR_UPDATE = True
MASTER_RESTARTED = True
MASTER_RESETTED = True

MASTER_PROCESS_STARTED = 0
UPDATE_READY_FOR_DOWNLOAD = 1
DISCOVER_MODE_ACTIVATED = True
DISCOVER_MODE_DEACTIVATED = False
MASTER_PROCESS_ERROR = 4
CANCEL_UPDATE = 5

# nocice codes to master process
UPDATE_PACKAGE_DOWNLOADED = 1
INSUFFICIENT_MEMORY = 2
INSUFFICIENT_SPACE = 3

# led blink pattern
LED_WAITING_TIME = 1  # waiting time should longer than all below
ALWAYS_ON = (0, 0)
LONG_BLINK = (0.1, 0.8)
SHORT_BLINK = (0.2, 0.2)
HIGH_FREQ_BLINK = (0.05, 0.05)

# notify timeout
NOTIFY_NUMBER_OF_TRY = 5  # 次
NOTIFY_TIMEOUT = 5  # 秒

# ping timeout
PING_MAX_FAIL_TIMES = 2  # 次
PING_INTERVAL = 20  # 秒
PING_TIMEOUT = 0.5  # 秒

# download timeout
DOWNLOAD_TIMEOUT = 20

# kill waiting time
KILLING_WAITING_TIME = 5

# request for updating
UPDATING_ACCEPTED = 0
UPDATING_REFUSED = 1
CANCELLING_ACCEPTED = 0
CANCELLING_REFUSED = 1

# progress
PROGRESS_DELAY = 0.6
REPORT_PROGRESS_INTERVAL = 0.5

# led pattern
# depending on wiring
# for example, one may wire the led which will be lighened by gpio.LOW
# while for internal STATUS_LED, this is reversed
DARK = 0
LIGHT = 1

class Respond:
    def __init__(self):
        self.payload = None

class Monitor:
    def __init__(self, config=None):

        self.config = config = config or {}
        [config.setdefault(k, v) for k, v in default_config.items()]

        try:
            globals().update(importlib.import_module(config.get("environ")).__dict__)
        except:
            pass

        self.rpc_server = uri = config.get("rpc_server")
        self.client = hprose.HttpClient(uri)

        self.host = host = config.get("host")
        self.port = port = config.get("port")
        self.server = server = hprose.HttpServer(host=host, port=port)
        server.addFunctions([
            self.notice,
            self.update,
            self.isUpdating,
            self.cancelUpdate,
            self.isCancellingUpdate,
            self.readGPIO,
            self.listenGPIO,
            self.cancelListenGPIO,
            self.writeGPIO
        ])

        self.gpio = {}
        self.led_stop = False
        self.led_current_blink = ()
        self.monitor_stop = False
        self.ping_enabled = False
        self.master_pid = None

        self.tid = None
        self.update_progress = (0, "", 0)
        self.update_cancelling = False
        self.enable_report_update_progress = False

        # self.device_on_going = None
        self.mass_storage_usbdev_listerner = MassStorageUSBListerner()

        self.debug = config.get("debug")

        self.logfile = config.get("logfile")
        if self.logfile:
            with open(self.logfile, "w") as f:
                print("", file=f)

        atexit.register(self.atexit)

        self.discover_off()

        self.log("[  MO-INFO  ] Monitor initialized . Confirgurations: \n%s" % json.dumps(self.config, indent=4))

    def atexit(self):
        self.dark_led()
        time.sleep(1)
        self.log("[  MO-INFO  ] Monitor quit .")

    def start(self):
        # threading.Thread(target=self.server.start, args=()).start()
        try:
            self.init_gpio_monitoring()
            self.start_gpio_monitoring()
            self.blink_led(*LONG_BLINK)
            # self.start_env_monitoring()
            self.check_abnormal_updating()
            self.start_usbdev_listerning()
            self.start_local_rpc_server()
            self._start_ping()
        except KeyboardInterrupt:
            self.led_stop = True
            self.monitor_stop = True
            time.sleep(0.1)
            self.log("[  MO-INFO  ] Monitor stopped by user .")

    def start_env_monitoring(self):
        threading.Thread(target=self._start_env_monitoring, args=()).start()

    def _start_env_monitoring(self):
        while not self.monitor_stop:
            self.log("[  MO-INFO  ] <FAKE> ENV MONITORING ...")
            time.sleep(1)
        self.log("[  MO-INFO  ] ENV MONITORING STOPPED .")

    def start_local_rpc_server(self):
        threading.Thread(target=self._start_local_rpc_server, args=()).start()

    def _start_local_rpc_server(self):
        try:
            self.server.start()
        except Exception as E:
            self.log("[  MO-ERROR  ] Local rpc server failed to start : %s" % E)
        # except KeyboardInterrupt:
        #     self.simulator_stop = True
        #     time.sleep(1)
        #     self.log("[  MO-INFO  ] Simulator stopped by user .")
        # while not self.monitor_stop:
        #     self.log("[  MO-INFO  ] <FAKE> LOCAL RPC SERVER RUNNING ...")
        #     time.sleep(1)
        # self.log("[  MO-INFO  ]  <FAKE> LOCAL RPC SERVER STOPPED .")
    
    def check_abnormal_updating(self):
        self.log("[  MO-INFO  ] Checking abnormal updating ...")
        try:
            progress_pickled = json.load(open(self.config.get("picklefile"), "r"))
        except:
            progress_pickled = {}

        # 恢复进度
        # 逻辑：
        #     辅助进程如果重启，亦视为断电，恢复出来的进度如果不是 100，则必然为异常
        #     辅助进程如果异常退出，或许来不及将异常位置为 0，故在此处应将其置为 0
        self.tid = progress_pickled.get("tid")
        update_progress = progress_pickled.get("progress", self.update_progress)

        if 100 > update_progress[0] >= 90-1:
            self.log("[  MO-WARN  ] Found abnormal updating (%s), recovery is to be performed ." % (update_progress,))
            self.kill()  # 发现升级异常，不论是正在运行与否，一律终止后恢复到升级前
            self.recover()  # √
            update_progress = (update_progress[0], update_progress[1], 0)
        elif 100 != update_progress[0] != 0:
            self.log("[  MO-WARN  ] Found abnormal updating (%s), but recovery is no needed to be performed ." % (update_progress,))
            update_progress = (update_progress[0], update_progress[1], 0)
        
        if update_progress[0] != 0: self.report_update_progress(update_progress)

        self.log("[  MO-INFO  ] Checking abnormal updating finished .")

    def start_usbdev_listerning(self):

        listerner = self.mass_storage_usbdev_listerner

        # def callback_on_plug_out(device):
            # threading.Thread(target=listerner.start, args=({"on_plug_in": callback_on_plug_in},)).start()
            # if self.device_on_going == device:
            #     self.log("[  MO-INFO  ] Device <%s> is the on-going one, plugging out results in restarting listening ." % device)
            #     self.device_on_going = None
            #     threading.Thread(target=listerner.start, args=({"on_plug_in": callback_on_plug_in},)).start()
            # else:
            #     self.log("[  MO-INFO  ] Device <%s> not the on-going one, plugging out results nothing ." % device)

        def callback_on_plug_in(device):

            # if not self.device_on_going:
            #     self.device_on_going = device
            # else:
            #     self.log("[  MO-INFO  ] device <%s> is on going, <%s> is ignored ." % (self.device_on_going, device))
            #     return

            listerner.stop()

            try:
                point = self.config.get("mount_dir")
                ShellCommander.mount(device, point)
            except Exception as E:
                self.log("[  MO-ERROR  ] Error mounting %s on %s: \n\t%s" % (device, point, E))
                # print(traceback.format_exc())

            update_pkg_path = os.path.join(point, self.config.get("update_pkg_name"))
            if os.path.isfile(update_pkg_path):
                self.log("[  MO-INFO  ] Updating from a massive storage device is to be performed .")

                self.update_cancelling = False
                self.stop_ping()

                try:
                    self.__update(src=update_pkg_path)
                    # print("meow !")
                    time.sleep(5)
                except Exception as E:
                    self.report_update_progress((self.update_progress[0] - 1, "Error updating : %s" % E, 0))
                    self.log("[  MO-INFO  ] PRODUCT FAILED TO UPDATE : %s" % E)
                    self.blink_led(*SHORT_BLINK)
                    if self.update_progress[0] >= 90-1:
                        self.recover()  # √
                    else:
                        self.log("[  MO-INFO  ] PRODUCT UPDATE PROGRESS < 90% DON\'T NEED RECOVERY .")
                    # print("\n%s\n" % traceback.format_exc())

                self.update_cancelling = False
                threading.Thread(target=self.start_ping).start()  # √

            else:
                self.log("[  MO-INFO  ] No update package found in the massive storate device, ignored .")

            try:
                ShellCommander.umount(device, point)
            except Exception as E:
                self.log("[  MO-ERROR  ] Error unmounting %s on %s: \n\t%s" % (device, point, E))
                # print(traceback.format_exc())
            #
            threading.Thread(target=listerner.start, args=({"on_plug_in": callback_on_plug_in},)).start()

        threading.Thread(target=listerner.start, args=({"on_plug_in": callback_on_plug_in},)).start()

        # 注意：升级过程中插入新的存储设备，不会对升级过程造成影响，也不会发生额外的升级过程，即被忽略
        #      只有当前升级过程完成后，拔出该存储设备，并重新拔插升级过程中插入的存储设备，才会基于此存储设备发生升级

    def stop_usbdev_listerning(self):
        self.mass_storage_usbdev_listerner.stop()

    # @LOCAL_RPC
    def notice(self, code=-1, detail=None):
        detail = detail or {}

        if code == MASTER_PROCESS_STARTED:
            self.log("[  MO-INFO  ] Master process is stared .")
            self.discover_off()  # 启动，说明之前停止，不论之前是否为发现模式，都置其为 False
            self.blink_led(*ALWAYS_ON)
            return True
        elif code == UPDATE_READY_FOR_DOWNLOAD:
            return self.update(detail)
        elif code == DISCOVER_MODE_ACTIVATED:
            self.log("[  MO-INFO  ] Discover mode activated .")
            return self.blink_led(*LONG_BLINK)
            # do some thing that to be determined
        elif code == DISCOVER_MODE_DEACTIVATED:
            self.log("[  MO-INFO  ] Discover mode deactivated .")
            return self.blink_led(*ALWAYS_ON)
            # do some thing that to be determined
        elif code == MASTER_PROCESS_ERROR:
            self.log("[  MO-INFO  ] Master process error .")
            return self.blink_led(*SHORT_BLINK)
            # do some thing that to be determined like showing detail errors
        elif code == CANCEL_UPDATE:
            return self.cancelUpdate()

    # @LOCAL_RPC
    def readGPIO(self, pin):
        return "to be done"
    
    # @LOCAL_RPC
    def listenGPIO(self, pin, type):
        return "to be done"
    
    # @LOCAL_RPC
    def cancelListenGPIO(self, pin, type):
        return "to be done"
    
    # @LOCAL_RPC
    def writeGPIO(self, pin, value):
        return "to be done"

    def init_gpio_monitoring(self):
        # Init gpio module
        gpio.init()
        self.log("[  MO-INFO  ] GPIO initialized.")

        # Set directions
        gpio_inputs = self.config.get("gpio_inputs", {})
        gpio_outputs = self.config.get("gpio_outputs", {})

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
        self.log("[  MO-INFO  ] GPIO configured:"
            "\n\tgpio_inputs:"
            "\n\t\t%s"
            "\n\tgpio_outputs:"
            "\n\t\t%s" % ("emitting", "emitting"))

    def start_gpio_monitoring(self):
        threading.Thread(target=self._start_gpio_monitoring, args=()).start()
    
    # @GPIO
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
            
            meow = 1
            while (100 != self.update_progress[0] != 0) and (self.update_progress[2] != 0):
                # 升级 正常（[2]==0） 进行中（100!=[0]!=0）
                if meow:
                    self.log("[  MO-INFO  ] UPDATING, ALL BUTTONS DISABLED .")
                    meow = 0
            if meow == 0: self.log("[  MO-INFO  ] ALL BUTTONS ENABLED .")

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
                                self.log("[  MO-DBUG  ] Reset button pressed for: %s" % time_kept_reset)
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
                                self.log("[  MO-DBUG  ] Set button pressed for: %s" % time_kept_set)
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
                        self.log("[  MO-DBUG  ] Reset with Set button pressed for %s secs" % time_kept_two_btns)
                        if time_kept_two_btns >= 3:
                            self.update_cancelling = False
                            self.stop_ping()
                            self.stop_usbdev_listerning()
                            
                            self.recover()

                            self.update_cancelling = False
                            threading.Thread(target=self.start_ping).start()  # √
                            self.start_usbdev_listerning()

                    # 然后是 reset 键
                    elif time_kept_reset >= 5 and time_kept_reset < 10:
                        self.reset(USERPASSWD)
                    
                    elif time_kept_reset >= 10:
                        self.reset(USERDATA)

                    # 最后是 set 键
                    elif time_kept_set > 0 and time_kept_set < 3:
                        self.restart()
                    
                    elif time_kept_set >= 3:
                        self.discover_on()
            
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
                self.blink_led(*led_blink_last)
                led_blink_last = ()

    def dark_led(self):
        self.led_stop = True
        time.sleep(LED_WAITING_TIME)  # waiting led to stop
        self.led_stop = False
        gpio.output(self.gpio.get("led"), DARK)
        self.led_current_blink = ()

    def blink_led(self, interval_dark=0, interval_light=0):
        self.log("[  MO-DBUG  ] led_current_blink = (%s, %s)" % (interval_dark, interval_light))
        self.dark_led()

        gpio.output(self.gpio.get("led"), LIGHT)
        
        if interval_dark and interval_light:
            threading.Thread(target=self._blink_led, args=(interval_dark, interval_light)).start()

        self.led_current_blink = (interval_dark, interval_light)

        return True

    def _blink_led(self, interval_dark=0, interval_light=0):
        zerone = cycle((DARK, LIGHT))
        value = LIGHT
        while not self.led_stop:
            if value:
                time.sleep(interval_light)
            else:
                time.sleep(interval_dark)
            value = next(zerone)
            gpio.output(self.gpio.get("led"), value)
        self.led_stop = False

    # @RPC
    def reset(self, type):  
        if type == USERPASSWD:
            self.blink_led(*LONG_BLINK)
            something = "Passwd"
        elif type == USERDATA:
            self.blink_led(*SHORT_BLINK)
            something = "Userdata"
        
        self.log("[  MO-INFO  ] %s is going to be reset !" % something)

        self.log("[  MO-INFO  ] <FAKE> CALLING RPC.RESET FUNCTION .")
        time.sleep(1)
        # if calling returns MASTER_RESETTED
        self.blink_led(*ALWAYS_ON)
        
        self.log("[  MO-INFO  ] %s reset !" % something)

    # @RPC
    def restart(self):
        self.log("[  MO-INFO  ] Restart is going to be activated !")

        self.blink_led(*LONG_BLINK)
        
        if self.debug:
            self.log("[  MO-INFO  ] <FAKE> CALLING RPC.RESTART FUNCTION .")
            time.sleep(1)
            result = MASTER_RESTARTED
        else:
            try:
                result = self.client.restart()
            except Exception as E:
                result = None
                self.log("[  MO-WARN  ] Restart Error: %s" % E)
        # if calling returns MASTER_RESTARTED
        if result == MASTER_RESTARTED:
            self.blink_led(*LONG_BLINK)
        else:  # 产品出错
            self.blink_led(*SHORT_BLINK)

        self.log("[  MO-INFO  ] Restart activated !")

    # @RPC
    def discover_on(self):
        if self.discover_mode_on:
            self.log("[  MO-INFO  ] Discover mode is on, re-activating it is not allowed .")
            return
            
        self.log("[  MO-INFO  ] Discover mode is going to be activated !")

        if self.debug:
            self.log("[  MO-INFO  ] <FAKE> CALLING RPC.DISCOVER FUNCTION .")
            time.sleep(1)
            result = DISCOVER_MODE_ACTIVATED
        else:
            try:
                result = self.client.discover()
            except Exception as E:
                result = None
                self.log("[  MO-WARN  ] Discover Error: %s" % E)

        # if calling returns DISCOVER_MODE_ACTIVATED
        if result == DISCOVER_MODE_ACTIVATED:
            self.discover_mode_on = True
            self.blink_led(*LONG_BLINK)
            self.log("[  MO-INFO  ] Discover mode activated !")
            # DISCOVER_MODE_DEACTIVATED will be notified by master
        else:
            self.log("[  MO-INFO  ] Discover mode FAILED activated !")

    def discover_off(self):
        self.discover_mode_on = False
        self.log("[  MO-INFO  ] Discover mode is off .")

    # def ping(self):
    #     threading.Thread(target=self._ping, args=()).start()

    # @LOCAL
    def start_ping(self):
        try:
            self._start_ping()
        except KeyboardInterrupt:
            self.dark_led()
            self.log("[  MO-INFO  ] Monitor stopped by user .")

    # @LOCAL
    def _start_ping(self):
        self.log("[  MO-INFO  ] PING STARTED .")
        self.ping_enabled = True
        ping_fail = 0
        killed = False
        first_ping = True
        
        while not self.monitor_stop and self.ping_enabled:
            self.log("[  MO-INFO  ] PING ...")                
            if self.debug:
                pass
            else:
                try:
                    pong = self.try_ping(PING_TIMEOUT)
                except:
                    pong = None

                if not self.ping_enabled: break

                if pong:
                    self.master_pid = pong
                    ping_fail = 0
                    killed = False
                    if self.led_current_blink != ALWAYS_ON:
                        self.blink_led(*ALWAYS_ON)  # 正常工作
                    if first_ping:
                        self.log("[  MO-INFO  ] FIRST PING !") 
                        if self.update_progress[0] != 0: self.reset_update_progress()
                        first_ping = False
                    # if self.update_progress[0] != 0: 
                    #     self.reset_update_progress()
                else:
                    ping_fail += 1
                    if self.led_current_blink != LONG_BLINK:
                        self.blink_led(*LONG_BLINK)
                    self.log("[  MO-INFO  ] PING FAILED(%s)" % ping_fail)

                if ping_fail > PING_MAX_FAIL_TIMES:
                    self.master_pid = None
                    killed = True
                    self.kill()
                    if self.led_current_blink != SHORT_BLINK:
                        self.blink_led(*SHORT_BLINK)  # 产品出错
                        
            if not self.master_pid and not self.debug:
                threading.Thread(target=self.revive).start()
            time.sleep(PING_INTERVAL)
                
        self.log("[  MO-INFO  ] PING STOPPED .")
    
    # @LOCAL
    def stop_ping(self):
        self.ping_enabled = False

    # @LOCAL
    def kill(self, pid=None):
        if self.debug:
            self.log("[  MO-INFO  ] <FAKE> KILLING MASTER .")
        else:
            try:
                self.log("[  MO-INFO  ] KILLING MASTER ...")
                pid = int(pid)
                os.system("sudo kill -9 %s" % pid)
                time.sleep(KILLING_WAITING_TIME)
                self.log("[  MO-INFO  ] KILLED MASTER .")
            except:
                self.log("[  MO-INFO  ] NO MASTER PID PROVIDED, TRY KILL CMD ...")
                try:
                    kill_cmd = self.config.get("kill_cmd")
                    os.system(kill_cmd)
                    time.sleep(KILLING_WAITING_TIME)
                    self.log("[  MO-INFO  ] KILLED MASTER .")
                except:
                    self.log("[  MO-INFO  ] FAILED KILLING MASTER .")
                
    # @LOCAL
    def revive(self):
        start_cmd = self.config.get("start_cmd")
        if start_cmd and not self.debug:
            os.system(start_cmd) 
            self.log("[  MO-INFO  ] REVIVED MASTER .")
        else:
            self.log("[  MO-INFO  ] <FAKE> REVIVED MASTER .")

    # @RPC
    def notify(self, code=-1, detail=None, respond=None):
        detail = detail or {}
        if self.debug:
            self.log("[  MO-INFO  ] <FAKE> CALLING RPC.NOTICE FUNCTION .")
            time.sleep(0.1)
            self.log("[  MO-INFO  ] <FAKE> CALLED RPC.NOTICE FUNCTION .")
        else:
            self.log("[  MO-INFO  ] CALLING RPC.NOTICE FUNCTION .")
            try:
                respond_data = self.client.notice(code, detail)
                if respond: respond.payload = respond_data
                self.log("[  MO-INFO  ] CALLED RPC.NOTICE FUNCTION .")
            except Exception as E:
                self.log("[  MO-INFO  ] FAILED CALLING RPC.NOTICE FUNCTION : %s" % E)

    # @RPC (not available yet)
    def on_gpio(self, pin, type, value):
        self.log("[  MO-INFO  ] <FAKE> CALLING RPC.ONGPIO FUNCTION .")
    
    # @LOCAL_RPC
    def isUpdating(self):
        return self.update_progress[0] != 0

    # @LOCAL_RPC
    def isCancellingUpdate(self):
        return self.update_cancelling

    # @LOCAL_RPC
    def cancelUpdate(self):
        # 已有中止事务在进行 → 拒绝
        if self.update_cancelling:
            self.log("[  MO-INFO  ] Cancelling is refused since an existed cancelling is ongoing .")
            return {
                "status": CANCELLING_REFUSED,
                "message": "Cancelling is refused: An Cancelling is on going ."
            }
        
        # 当前没有中止事务 → 接受
        self.log("[  MO-INFO  ] Cancelling is accepted .")
        self.update_cancelling = True
        return {
            "status": CANCELLING_ACCEPTED,
            "message": "Cancelling is accepted ."
        }

    # @LOCAL_RPC
    def is_update_cancelling(self):
        if self.update_cancelling:  # 升级被中止
            self.report_update_progress((self.update_progress[0] - 1, "Error updating : Cancelled by user .", 0))
            self.log("[  MO-INFO  ] PRODUCT FAILED TO UPDATE : CANCELLED BY USER .")
            # self.blink_led(*LONG_BLINK)
            # self.update_cancelling = False
            # self.start_ping()
            return True
        else:
            return False

    # @LOCAL_RPC
    def update(self, info=None):
        info = info or {}

        # 已有升级事务在进行 → 拒绝
        if self.tid:
            self.log("[  MO-INFO  ] Updating is refused since an existed updating is ongoing .")
            return {
                "status": UPDATING_REFUSED,
                "message": "Updating is refused: An Updating is on going ."
            }

        # 当前没有升级事务
        self.tid = info.get("tid")

        # 没有提供事务 id → 拒绝
        if not self.tid:  
            self.log("[  MO-INFO  ] Updating is refused since no tid .")
            return {
                "status": UPDATING_REFUSED,
                "message": "Updating refused: A tid is required ."
            }
        
        # 当前没有升级事务，提供了事务 id → 接受
        self.stop_ping()  # 停止 ping
        self.stop_usbdev_listerning()  # 停止 listerning
        self.log("[  MO-INFO  ] Updating is accepted: Downloading update package ...")
        threading.Thread(target=self._update, args=(info.get("url"),)).start()
        return {
            "status": UPDATING_ACCEPTED,
            "message": "Updating is accepted: Downloading update package ..."
        }

    # @LOCAL
    def _update(self, url="", dest=None):

        self.update_cancelling = False

        self.report_update_progress((10, "Preparing ...", 1))  # 开始准备：总进度 10%

        dest = dest or self.config.get("download_dir")
        if not os.path.isdir(dest): os.makedirs(dest)  # 创建未有
        update_pkg_save_path = os.path.join(dest, self.config.get("update_pkg_name"))
        if os.path.isfile(update_pkg_save_path): os.remove(update_pkg_save_path)  # 删除已有
        # time.sleep(1)
        # self.stop_ping()  # 停止 ping
        # self.report_update_progress((20, "Prepared .", 1))  # 准备完毕：总进度 20%

        if self.debug:
            self.log("[  MO-INFO  ] <FAKE> DOWNLOADING FROM %s ..." % url)
            time.sleep(5)
            self.log("[  MO-INFO  ] <FAKE> DOWNLOADED FROM %s TO %s." % (url, update_pkg_save_path))
            self.start_ping()  # √
        else:
            self.log("[  MO-INFO  ] DOWNLOADING FROM %s ..." % url)
            
            try:
                # ############################ DOWNLOADING ... ############################
                self.report_update_progress((20, "Downloading ...", 1))  # 开始下载：总进度 30%

                r = requests.get(url, stream=True, timeout=DOWNLOAD_TIMEOUT)
                f = open(update_pkg_save_path, "wb")
                for chunk in r.iter_content(chunk_size=512):
                    if chunk:
                        f.write(chunk)
                f.close()

                # self.report_update_progress((10, "Successfully downloaded .", 1))  # 下载完毕：总进度 10%
                
                if not os.path.isfile(update_pkg_save_path): raise Exception("Download seems completed but downloaded is missing .")

                self.log("[  MO-INFO  ] SUCCESSFULLY DOWNLOADED FROM %s TO %s ." % (url, update_pkg_save_path))
                # ############################## DOWNLOADED . #############################

                try:
                    if not self.is_update_cancelling(): self.__update()
                except Exception as E:
                    self.report_update_progress((self.update_progress[0] - 1, "Error updating : %s" % E, 0))
                    self.log("[  MO-INFO  ] PRODUCT FAILED TO UPDATE : %s" % E)
                    self.blink_led(*SHORT_BLINK)
                    if self.update_progress[0] >= 90-1:
                        self.recover()  # √
                    else:
                        self.log("[  MO-INFO  ] PRODUCT UPDATE PROGRESS < 90% DON\'T NEED RECOVERY .")
                    # print("\n%s\n" % traceback.format_exc())
                    return

            except requests.exceptions.Timeout:
                self.log("[  MO-INFO  ] FAILED DOWNLOADING FROM %s : %s" % (url, "Timeout"))
                self.report_update_progress((self.update_progress[0] - 1, "Error downloading : %s" % "Timeout", 0))

            except Exception as E:
                self.log("[  MO-INFO  ] FAILED DOWNLOADING FROM %s : %s" % (url, E))
                self.report_update_progress((self.update_progress[0] - 1, "Error downloading : %s" % E, 0))
                # print("\n%s\n" % traceback.format_exc())
            
            # NO MATTER WHAT, START PING
            self.blink_led(*LONG_BLINK)
            self.update_cancelling = False
            self.start_usbdev_listerning()
            self.start_ping()  # √

    # @LOCAL
    def __update(self, src=None):
        """
        unpack → cover
        """
        self.blink_led(*HIGH_FREQ_BLINK)
        if self.debug:
            self.log("[  MO-INFO  ] <FAKE> PRODUCT UPDATING ...")
            time.sleep(5)
            self.log("[  MO-INFO  ] <FAKE> PRODUCT UPDATED .")
        else:
            self.log("[  MO-INFO  ] PRODUCT UPDATING ...")
            # "master_dir"     : "/path/to/vigateway",
            # "download_dir"   : "/path/to/download",
            # "backup_dir"     : "/path/to/bkup",
            # "update_pkg_name": "vigateway.zip",
            # "bakcup_pkg_name"  : "vigateway_bkup_latest.zip"
            src = src or os.path.join(self.config.get("download_dir"), self.config.get("update_pkg_name"))
            dest = self.config.get("master_dir")
            bkup = self.config.get("backup_dir")
            bkup_excludes = self.config.get("backup_excludes")
            bkup_file_name = self.config.get("bakcup_pkg_name")
            unzipped = src + "_unzipped"
            errors = []

            updateManager = UpdateManager(src, dest, bkup, bkup_file_name, bkup_excludes) # 实例化
            
            self.report_update_progress((30, "Unpacking ...", 1))  # 正在解压：总进度 20%
            errors.extend(updateManager.un_zip()) # 解压
            if errors: raise Exception("\n\t".join(errors))
            # self.report_update_progress((30, "Successfully unpacked .", 1))  # 解压完毕：总进度 30%

            if self.is_update_cancelling(): return  # 中止升级

            self.report_update_progress((40, "Reading information ...", 1))  # 正在读取版本信息：总进度 40%
            # 读取
            original_version_info = json.load(open(os.path.join(dest, "version.json")))
            version_info = json.load(open(os.path.join(unzipped, "version.json")))  
            # self.report_update_progress((50, "Successfully Read version information .", 1))  # 读取版本信息成功：总进度 50%

            if self.is_update_cancelling(): return  # 中止升级

            ori_version = original_version_info.get("version")
            new_version = version_info.get("version")
            if ori_version == new_version:
                tips = "No need updating: from *%s* to *%s*, cancelled ." % (ori_version, new_version)
                self.log("[  MO-INFO  ] %s" % tips)
                self.report_update_progress((39, tips, 0))  # 升级完毕：总进度 100%
                # self.report_update_progress((100, tips, new_version))  # 升级完毕：总进度 100%
                return
            else:
                self.log("[  MO-INFO  ] Updating plan: from *%s* to *%s* ." % (ori_version, new_version))

            self.report_update_progress((50, "Verifying ...", 1))  # 正在校验：总进度 60%
            self.verify(unzipped_pkg=unzipped, version_info=version_info)
            # self.report_update_progress((70, "Successfully Verified ...", 1))  # 校验成功：总进度 70%

            if self.is_update_cancelling(): return  # 中止升级

            # ############################ NOTIFYING ... ############################
            if self.try_notify(NOTIFY_TIMEOUT, NOTIFY_NUMBER_OF_TRY, args=(UPDATE_PACKAGE_DOWNLOADED, {"tid": self.tid}), success_key=MASTER_READY_FOR_UPDATE, tips="MASTER NOT YET READY FOR UPDATE") != MASTER_READY_FOR_UPDATE:
                self.log("[  MO-WARN  ] Not responding from Master process, forciblly killing it .")
                self.kill()     
                self.log("[  MO-WARN  ] Not responding from Master process, forciblly killed .")  
            # ############################## NOTIFIED . #############################

            self.report_update_progress((60, "Backupping ...", 1))  # 正在备份：总进度 80%
            errors.extend(updateManager.step_bkup()) # 备份

            self.report_update_progress((90, "Updating ...", 1))  # 正在升级：总进度 90%
            errors.extend(updateManager.step_update()) # 升级

            if errors: raise Exception("\n\t".join(errors))
            self.report_update_progress((100, "Successfully backupped and updated .", new_version))  # 备份并升级完毕：总进度 100%
            
            self.log("[  MO-INFO  ] PRODUCT SUCCESSFULLY UPDATED .")
            self.blink_led(*LONG_BLINK)

    # @LOCAL
    def report_update_progress(self, progress, delay=PROGRESS_DELAY):
        self.update_progress = progress
        try:
            json.dump({"tid": self.tid, "progress": self.update_progress}, open(self.config.get("picklefile"), "w"))  # 若不存在则自动创建
            self.client.progress(self.tid, *progress)
            self.log("[  MO-INFO  ] <%s>Progress reported : %s" % (self.tid, progress,))
        except Exception as E:
            self.log("[  MO-ERROR  ] Error <%s>progress reporting : %s" % (self.tid, progress,))
            self.log("\t\t%s" % E)

    def reset_update_progress(self):
        self.log("[  MO-INFO  ] Progress resetting : %s" % (self.update_progress,))
        self.update_progress = (0, "", 0)  # 重置 进度
        self.tid = None  # 重置 事务 id
        json.dump({"tid": self.tid, "progress": self.update_progress}, open(self.config.get("picklefile"), "w"))  # 重置 进度持久化
        self.log("[  MO-INFO  ] Progress reset : %s" % (self.update_progress,))

    # @LOCAL
    def recover(self):
        """
        unpack → cover
        """

        # self.stop_ping()

        self.blink_led(*SHORT_BLINK)
        if self.debug:
            self.log("[  MO-INFO  ] Recovery is going to be activated !")
            time.sleep(5)
            self.log("[  MO-INFO  ] <FAKE> RECOVERY ACTIVATED .")
        else:
            self.log("[  MO-INFO  ] PRODUCT RECOVERING ...")
            # "master_dir"     : "/path/to/vigateway",
            # "download_dir"   : "/path/to/download",
            # "backup_dir"     : "/path/to/bkup",
            # "update_pkg_name": "vigateway.zip",
            # "bakcup_pkg_name"  : "vigateway_bkup_latest.zip"
            src = os.path.join(self.config.get("backup_dir"), self.config.get("bakcup_pkg_name"))
            dist = self.config.get("master_dir")
            errors = []

            try:
                if not os.path.isfile(src): raise Exception("NO BACKUP PACKAGE FOUND .")
                updateManager = UpdateManager(src, dist) # 实例化
                errors.extend(updateManager.un_zip()) # 解压
                errors.extend(updateManager.update()) # 更新
                self.log("[  MO-INFO  ] PRODUCT RECOVERED .")
                self.blink_led(*LONG_BLINK)
                threading.Thread(target=self.revive).start()
            except Exception as E:
                errors.append("%s" % E)
            
            if errors:
                self.log("[  MO-INFO  ] PRODUCT FAILED RECOVERED : %s" % "\n\t".join(errors))
                self.blink_led(*SHORT_BLINK)

            # self.start_ping()

    # @LOCAL
    def verify(self, unzipped_pkg, version_info):
        files_md5_comb = "".join(list(map(lambda x: md5_from_file(os.path.join(unzipped_pkg, x)), self.config.get("verifying_files"))))
        if version_info.get("md5") == md5_from_string(files_md5_comb):
            return True
        else:
            raise Exception("MD5 not matched")

    # ################################## DEPRECATED #####################################
    # X@LOCAL
    def start_update_progress(self):
        self.enable_report_update_progress = True
        threading.Thread(target=self._update_progress, args=()).start()

    # X@LOCAL
    def stop_update_progress(self):
        self.enable_report_update_progress = False

    # X@LOCAL
    def _update_progress(self, interval=REPORT_PROGRESS_INTERVAL):
        self.log("[  MO-INFO  ] Progress on . @%s" % (self.update_progress,))
        interval = max(0.5, interval)
        
        def report_progress():
            self.log("[  MO-INFO  ] Progress reporing : %s" % (self.update_progress,))
            try:
                self.client.progress(self.tid, *self.update_progress)
            except Exception as E:
                self.log("[  MO-ERROR  ] Error progress reporting : %s" % (self.update_progress,))

        last_progress = None
        while self.enable_report_update_progress:
            if last_progress != self.update_progress:
                report_progress()
                json.dump({"tid": self.tid, "progress": self.update_progress}, open(self.config.get("picklefile"), "w"))  # 若不存在则自动创建
            last_progress = self.update_progress
            time.sleep(interval)
        
        report_progress()  # 报告 最后一条进度
        self.update_progress = (0, "", 0)  # 重置 进度
        self.tid = None  # 重置 事务 id
        json.dump({"tid": self.tid, "progress": self.update_progress}, open(self.config.get("picklefile"), "w"))  # 重置 进度持久化
        self.log("[  MO-INFO  ] Progress off . @%s" % (self.update_progress,))
    # ################################## DEPRECATED #####################################

    # @LOCAL
    def try_notify(self, timeout=0, number_of_try=0, interval=1, args=(), success_key="", tips="..."):
        respond = Respond()
        notify = threading.Thread(target=self.notify, args=(*args, respond))
        notify.start()
        notify.join(timeout=timeout)

        if respond.payload == success_key:
            return success_key
        
        remain_times = ("REMIANED %s" % number_of_try) if number_of_try else ""
        self.log("[  MO-INFO  ] %s . TRYING ... %s" % (tips, remain_times))
            
        if interval > 0: time.sleep(interval)
        if number_of_try <= 0:
            return respond.payload
        else:
            return self.try_notify(timeout, number_of_try - 1, interval, args, success_key, tips)

    # @LOCAL
    def try_ping(self, timeout):
        respond = Respond()
        notify = threading.Thread(target=self._ping, args=(respond,))
        notify.start()
        notify.join(timeout=timeout)
        self.log("[  MO-INFO  ] Ping-Pong report: %s" % respond.payload)
        return respond.payload

    # @LOCAL
    def _ping(self, respond):
        try:
            result = self.client.ping()
            self.log("[  MO-INFO  ] Ping-Pong result: %s" % result)
            respond.payload = result
        except Exception as E:
            self.log("[  MO-INFO  ] Ping-Pong error: %s" % E)
            respond.payload = None

    # @LOCAL
    def log(self, logline, screen=False):
        logtime = time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(time.time()))
        logline = "[%s]%s" % (logtime, logline) 
        if self.logfile:
            with open(self.logfile, "a") as f:
                print(logline, file=f)
        if screen or not self.logfile: print(logline)

if __name__ == '__main__':

    try:
        config_file = sys.argv[1]
    except:
        config_file = "/usr/local/hyt/vigmonitor/mysetting.json"

    if os.path.isfile(config_file):
        print("[  MO-INFO  ] Configuration file selected: %s" % config_file)
        try:
            config = json.load(open(config_file))
            print("[  MO-INFO  ] Configuration file loaded: %s" % config_file)
        except Exception as E:
            print("[  MO-ERROR  ] Configuration file loading error: %s\n\t%s" % (E, config_file))
    else:
        print("[  MO-ERROR  ] Configuration file doesn't exist: %s" % config_file)
        config = {}

    not_specified = "ksjdg;oahg"
    for k, v in default_config.items():
        specified = config.get(k, not_specified)
        if specified == not_specified:
            config[k] = v

    Monitor(config).start()

# example
# {
#     "rpc_server": "http://127.0.0.1:8282/",
#     "port": 8181,
    
#     "gpio_inputs": {
#         "set": "PA10",
#         "reset": "PA9"
#     },
#     "gpio_outputs": {
#         "led": "STATUS_LED"
#     },
    
#     "master_dir": "/home/catcuts/project/isht/test/vigserver_running",
#     "download_dir": "/home/catcuts/project/isht/test/download",
#     "backup_dir": "/home/catcuts/project/isht/test/backup",
#     "update_pkg_name": "vigserver.zip",
#     "bakcup_pkg_name": "vigserver_bkup_latest.zip",

#     "verifying_files": [
#         "server.js",
#         "core/device/manager.js",
#         "core/eventbus/eventbus.js"
#     ],

#     "debug": true
# }
