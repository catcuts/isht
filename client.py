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
from itertools import cycle
from pyA20.gpio import gpio
from pyA20.gpio import port
from pyA20.gpio import connector

default_config = {
    # RPC
    "rpc_server": "http://127.0.0.1:8282/",
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
    "master_dir": "/home/catcuts/project/isht/test/vigserver_running",
    "download_dir": "/home/catcuts/project/isht/test/download",
    "backup_dir": "/home/catcuts/project/isht/test/backup",
    "update_pkg_name": "vigserver.zip",
    "bakcup_pkg_name": "vigserver_bkup_latest.zip",

    # MD5 VERIFICATION SPECIFIED FILES
    "verifying_files": [
        "server.js",
        "core/device/manager.js",
        "core/eventbus/eventbus.js"
    ],

    # START COMMAND
    # "start_cmd": "sudo python3.6 ./server.py",
    # "start_cmd": "sudo node /home/catcuts/project/isht/test/vigserver_running/start.js",

    # DBUG
    "debug": True
}

USERPASSWD = 0
USERDATA = 1

# notice codes from master process
MASTER_READY_FOR_UPDATE = 0
MASTER_RESTARTED = True
MASTER_RESETTED = True

MASTER_PROCESS_STARTED = 0
UPDATE_READY_FOR_DOWNLOAD = 1
DISCOVER_MODE_ACTIVATED = 2
DISCOVER_MODE_DEACTIVATED = 3
MASTER_PROCESS_ERROR = 4
CANCEL_UPDATE = 5

# nocice codes to master process
UPDATE_PACKAGE_DOWNLOADED = 1
INSUFFICIENT_MEMORY = 2
INSUFFICIENT_SPACE = 3

# led blink pattern
LED_WAITING_TIME = 1.5  # waiting time should longer than all below
ALWAYS_ON = (0, 0)
LONG_BLINK = (0.2, 1.2)
SHORT_BLINK = (0.2, 0.2)
HIGH_FREQ_BLINK = (0.05, 0.05)

# notify timeout
NOTIFY_NUMBER_OF_TRY = 10  # 次
NOTIFY_TIMEOUT = 5  # 秒

# ping timeout
PING_MAX_FAIL_TIMES = 8  # 次
PING_TIMEOUT = 0.5  # 秒

# download timeout
DOWNLOAD_TIMEOUT = 20

KILL_WAITING_TIME = 5

class Respond:
    def __init__(self):
        self.payload = None

class Monitor:
    def __init__(self, config=None):
        self.config = config = config or {}
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
        self.ping_enabled = False
        self.master_pid = None

        self.update_progress = (0, "", 0)
        self.update_cancelled = False

        self.debug = config.get("debug")

        print("[  MO-INFO  ] Monitor initialized . Confirgurations: \n%s" % json.dumps(self.config, indent=4))

    def start(self):
        # threading.Thread(target=self.server.start, args=()).start()
        try:
            self.init_gpio_monitoring()
            self.start_gpio_monitoring()
            self.blink_led(*LONG_BLINK)
            # self.start_env_monitoring()
            self.start_local_rpc_server()
            self.start_ping()
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
        try:
            self.server.start()
        except Exception as E:
            print("[  MO-ERROR  ] Local rpc server failed to start : %s" % E)
        # except KeyboardInterrupt:
        #     self.simulator_stop = True
        #     time.sleep(1)
        #     print("[  MO-INFO  ] Simulator stopped by user .")
        # while not self.monitor_stop:
        #     print("[  MO-INFO  ] <FAKE> LOCAL RPC SERVER RUNNING ...")
        #     time.sleep(1)
        # print("[  MO-INFO  ]  <FAKE> LOCAL RPC SERVER STOPPED .")
    
    # @LOCAL_RPC
    def notice(self, code=-1, detail=None):
        if code == MASTER_PROCESS_STARTED:
            print("[  MO-INFO  ] Master process is stared .")
            return self.blink_led(*ALWAYS_ON)
        elif code == UPDATE_READY_FOR_DOWNLOAD:
            print("[  MO-INFO  ] Downloading update package ...")
            threading.Thread(target=self.update, args=(detail.get("url"),)).start()
            return True
        elif code == DISCOVER_MODE_ACTIVATED:
            print("[  MO-INFO  ] Discover mode activated .")
            return self.blink_led(*LONG_BLINK)
            # do some thing that to be determined
        elif code == DISCOVER_MODE_DEACTIVATED:
            print("[  MO-INFO  ] Discover mode deactivated .")
            return self.blink_led(*ALWAYS_ON)
            # do some thing that to be determined
        elif code == MASTER_PROCESS_ERROR:
            print("[  MO-INFO  ] Mater process error .")
            return self.blink_led(*SHORT_BLINK)
            # do some thing that to be determined like showing detail errors
        elif code == CANCEL_UPDATE:
            print("[  MO-INFO  ] Cancelling update ...")
            self.update_cancelled = True
            return True

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
        print("[  MO-INFO  ] GPIO initialized.")

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
        print("[  MO-INFO  ] GPIO configured:"
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
                                print("[  MO-DBUG  ] Reset button pressed for: %s" % time_kept_reset)
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
                                print("[  MO-DBUG  ] Set button pressed for: %s" % time_kept_set)
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
                        print("[  MO-DBUG  ] Reset with Set button pressed for %s secs" % time_kept_two_btns)
                        if time_kept_two_btns >= 3:
                            self.recover()

                    # 然后是 reset 键
                    elif time_kept_reset >= 5 and time_kept_reset < 10:
                        self.reset(USERPASSWD)
                    
                    elif time_kept_reset >= 10:
                        self.reset(USERDATA)

                    # 最后是 set 键
                    elif time_kept_set > 0 and time_kept_set < 3:
                        self.restart()
                    
                    elif time_kept_set >= 3:
                        self.discover()
            
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
        gpio.output(self.gpio.get("led"), gpio.LOW)
        self.led_current_blink = ()

    def blink_led(self, interval_dark=0, interval_light=0):
        print("[  MO-DBUG  ] led_current_blink = (%s, %s)" % (interval_dark, interval_light))
        self.dark_led()

        value = gpio.HIGH
        gpio.output(self.gpio.get("led"), value)
        
        if interval_dark and interval_light:
            threading.Thread(target=self._blink_led, args=(interval_dark, interval_light)).start()

        self.led_current_blink = (interval_dark, interval_light)

        return True

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
        self.led_stop = False

    # @RPC
    def reset(self, type):  
        if type == USERPASSWD:
            self.blink_led(*LONG_BLINK)
            something = "Passwd"
        elif type == USERDATA:
            self.blink_led(*SHORT_BLINK)
            something = "Userdata"
        
        print("[  MO-INFO  ] %s is going to be reset !" % something)

        print("[  MO-INFO  ] <FAKE> CALLING RPC.RESET FUNCTION .")
        time.sleep(1)
        # if calling returns MASTER_RESETTED
        self.blink_led(*ALWAYS_ON)
        
        print("[  MO-INFO  ] %s reset !" % something)

    # @RPC
    def restart(self):
        print("[  MO-INFO  ] Restart is going to be activated !")

        self.blink_led(*LONG_BLINK)
        
        if self.debug:
            print("[  MO-INFO  ] <FAKE> CALLING RPC.RESTART FUNCTION .")
            time.sleep(1)
            result = MASTER_RESTARTED
        else:
            try:
                result = self.client.restart()
            except Exception as E:
                result = None
                print("[  MO-WARN  ] Restart Error: %s" % E)
        # if calling returns MASTER_RESTARTED
        if result == MASTER_RESTARTED:
            self.blink_led(*ALWAYS_ON)
        else:  # 产品出错
            self.blink_led(*SHORT_BLINK)

        print("[  MO-INFO  ] Restart activated !")

    # @RPC
    def discover(self):
        print("[  MO-INFO  ] Discover mode is going to be activated !")

        if self.debug:
            print("[  MO-INFO  ] <FAKE> CALLING RPC.DISCOVER FUNCTION .")
            time.sleep(1)
            result = DISCOVER_MODE_ACTIVATED
        else:
            try:
                result = self.client.discover()
            except Exception as E:
                result = None
                print("[  MO-WARN  ] Discover Error: %s" % E)

        # if calling returns DISCOVER_MODE_ACTIVATED
        if result == DISCOVER_MODE_ACTIVATED:
            self.blink_led(*LONG_BLINK)
            print("[  MO-INFO  ] Discover mode activated !")
            # DISCOVER_MODE_DEACTIVATED will be notified by master
        else:
            print("[  MO-INFO  ] Discover mode FAILED activated !")

    # def ping(self):
    #     threading.Thread(target=self._ping, args=()).start()

    # @RPC
    def start_ping(self):
        print("[  MO-INFO  ] PING STARTED .")
        self.ping_enabled = True
        ping_fail = 0
        killed = False

        self.revive()  # 启动主进程，后再 ping
        
        while not self.monitor_stop and self.ping_enabled:
            print("[  MO-INFO  ] PING ...")
            if self.debug:
                pass
            else:
                try:
                    pong = self.try_ping(PING_TIMEOUT)
                except:
                    pong = None
                if pong:
                    self.master_pid = pong
                    ping_fail = 0
                    killed = False
                    if self.led_current_blink != ALWAYS_ON:
                        self.blink_led(*ALWAYS_ON)  # 正常工作
                else:
                    ping_fail += 1

                if ping_fail > PING_MAX_FAIL_TIMES:
                    self.master_pid = None
                    killed = True
                    self.kill(self.master_pid)
                    if self.led_current_blink != SHORT_BLINK:
                        self.blink_led(*SHORT_BLINK)  # 产品出错
            time.sleep(20)
            if not self.master_pid and not self.debug:
                self.revive()
                
        print("[  MO-INFO  ] PING STOPPED .")
    
    # @LOCAL
    def stop_ping(self):
        self.ping_enabled = False

    # @LOCAL
    def kill(self, pid):
        if self.debug:
            print("[  MO-INFO  ] <FAKE> KILLING MASTER .")
        else:
            try:
                print("[  MO-INFO  ] KILLING MASTER ...")
                pid = int(pid)
                os.system("sudo kill -9 %s" % pid)
                time.sleep(KILL_WAITING_TIME)
                print("[  MO-INFO  ] KILLED MASTER .")
            except:
                print("[  MO-INFO  ] FAILED KILLING MASTER .")
                
    # @LOCAL
    def revive(self):
        start_cmd = self.config.get("start_cmd")
        if start_cmd and not self.debug:
            os.system(start_cmd) 
            print("[  MO-INFO  ] REVIVED MASTER .")
        else:
            print("[  MO-INFO  ] <FAKE> REVIVED MASTER .")

    # @RPC
    def notify(self, code=-1, detail=None, respond=None):
        detail = detail or {}
        if self.debug:
            print("[  MO-INFO  ] <FAKE> CALLING RPC.NOTICE FUNCTION .")
            time.sleep(0.1)
            print("[  MO-INFO  ] <FAKE> CALLED RPC.NOTICE FUNCTION .")
        else:
            print("[  MO-INFO  ] CALLING RPC.NOTICE FUNCTION .")
            try:
                respond_data = self.client.notice(code, detail)
                if respond: respond.payload = respond_data
                print("[  MO-INFO  ] CALLED RPC.NOTICE FUNCTION .")
            except Exception as E:
                print("[  MO-INFO  ] FAILED CALLING RPC.NOTICE FUNCTION : %s" % E)

    # @RPC (not available yet)
    def on_gpio(self, pin, type, value):
        print("[  MO-INFO  ] <FAKE> CALLING RPC.ONGPIO FUNCTION .")
    
    # @LOCAL
    def update(self, url="", dest=None):

        self.update_progress = (0, "Preparing ...", 1)  # 开始准备：总进度 0%
        self.start_update_progress()

        dest = dest or self.config.get("download_dir")
        if not os.path.isdir(dest): os.makedirs(dest)  # 创建未有
        update_pkg_save_path = os.path.join(dest, self.config.get("update_pkg_name"))
        if os.path.isfile(update_pkg_save_path): os.remove(update_pkg_save_path)  # 删除已有
        # time.sleep(1)
        self.stop_ping()  # 停止 ping
        self.update_progress = (2, "Prepared .", 1)  # 准备完毕：总进度 2%

        if self.debug:
            print("[  MO-INFO  ] <FAKE> DOWNLOADING FROM %s ..." % url)
            time.sleep(5)
            print("[  MO-INFO  ] <FAKE> DOWNLOADED FROM %s TO %s." % (url, update_pkg_save_path))
            self.start_ping()
        else:
            print("[  MO-INFO  ] DOWNLOADING FROM %s ..." % url)
            
            try:
                # ############################ DOWNLOADING ... ############################
                self.update_progress = (5, "Downloading ...", 1)  # 开始下载：总进度 5%

                r = requests.get(url, stream=True, timeout=DOWNLOAD_TIMEOUT)
                f = open(update_pkg_save_path, "wb")
                for chunk in r.iter_content(chunk_size=512):
                    if chunk:
                        f.write(chunk)
                f.close()

                self.update_progress = (10, "Successfully downloaded .", 1)  # 下载完毕：总进度 10%
                
                if not os.path.isfile(update_pkg_save_path): raise Exception("Download seems completed but downloaded is missing .")

                print("[  MO-INFO  ] SUCCESSFULLY DOWNLOADED FROM %s TO %s ." % (url, update_pkg_save_path))
                # ############################## DOWNLOADED . #############################

                try:
                    # ############################ NOTIFYING ... ############################
                    if self.try_notify(NOTIFY_TIMEOUT, NOTIFY_NUMBER_OF_TRY, args=(UPDATE_PACKAGE_DOWNLOADED, {}), success_key=MASTER_READY_FOR_UPDATE, tips="MASTER NOT YET READY FOR UPDATE") != MASTER_READY_FOR_UPDATE:
                        print("[  MO-WARNING  ] Not responding from Master process, forciblly killing it .")
                        self.kill(self.master_pid)     
                        print("[  MO-WARNING  ] Not responding from Master process, forciblly killed .")  
                    # ############################## NOTIFIED . #############################
                    self._update()
                    self.revive()
                except Exception as E:
                    self.update_progress = (self.update_progress[0] - 1, "Error updating : %s" % E, 0)
                    print("[  MO-INFO  ] PRODUCT FAILED TO UPDATE : %s" % E)
                    self.blink_led(*SHORT_BLINK)
                    if self.update_progress[0] >= 70:
                        self.recover()
                    else:
                        print("[  MO-INFO  ] PRODUCT UPDATE PROGRESS < 70% DON\'T NEED RECOVERY .")

            except requests.exceptions.Timeout:
                print("[  MO-INFO  ] FAILED DOWNLOADING FROM %s : %s" % (url, "Timeout"))
                self.update_progress = (self.update_progress[0] - 1, "Error downloading : %s" % "Timeout", 0)

            except Exception as E:
                print("[  MO-INFO  ] FAILED DOWNLOADING FROM %s : %s" % (url, E))
                self.update_progress = (self.update_progress[0] - 1, "Error downloading : %s" % E, 0)
            
            # NO MATTER WHAT, START PING
            self.start_ping()

    # @LOCAL
    def _update(self):
        """
        unpack → cover
        """
        self.blink_led(*HIGH_FREQ_BLINK)
        if self.debug:
            print("[  MO-INFO  ] <FAKE> PRODUCT UPDATING ...")
            time.sleep(5)
            print("[  MO-INFO  ] <FAKE> PRODUCT UPDATED .")
        else:
            print("[  MO-INFO  ] PRODUCT UPDATING ...")
            # "master_dir"     : "/path/to/vigateway",
            # "download_dir"   : "/path/to/download",
            # "backup_dir"     : "/path/to/bkup",
            # "update_pkg_name": "vigateway.zip",
            # "bakcup_pkg_name"  : "vigateway_bkup_latest.zip"
            src = os.path.join(self.config.get("download_dir"), self.config.get("update_pkg_name"))
            dest = self.config.get("master_dir")
            bkup = self.config.get("backup_dir")
            bkup_file_name = self.config.get("bakcup_pkg_name")
            unzipped = src + "_unzipped"
            errors = []

            updateManager = UpdateManager(src, dest, bkup, bkup_file_name) # 实例化
            
            self.update_progress = (20, "Unpacking ...", 1)  # 正在解压：总进度 20%
            errors.extend(updateManager.un_zip()) # 解压
            if errors: raise Exception("\n\t".join(errors))
            self.update_progress = (30, "Successfully unpacked .", 1)  # 解压完毕：总进度 30%

            self.update_progress = (40, "Reading version information ...", 1)  # 正在读取版本信息：总进度 40%
            # 读取
            original_version_info = json.load(open(os.path.join(dest, "version.json")))
            version_info = json.load(open(os.path.join(unzipped, "version.json")))  
            self.update_progress = (50, "Reading version information ...", 1)  # 读取版本信息成功：总进度 50%

            print("[  MO-INFO  ] Updating plan: from *%s* to *%s* ." % (original_version_info.get("version"), version_info.get("version")))

            self.update_progress = (60, "Verifying ...", 1)  # 正在校验：总进度 60%
            self.verify(unzipped_pkg=unzipped, version_info=version_info)
            self.update_progress = (70, "Successfully Verified ...", 1)  # 校验成功：总进度 70%

            self.update_progress = (80, "Backupping and Updating ...", 1)  # 正在备份并升级：总进度 80%
            errors.extend(updateManager.update()) # 更新
            if errors: raise Exception("\n\t".join(errors))
            self.update_progress = (100, "Successfully backupped and updated .", version_info.get("version"))  # 备份并升级完毕：总进度 100%
            
            print("[  MO-INFO  ] PRODUCT SUCCESSFULLY UPDATED .")
            self.blink_led(*LONG_BLINK)

    # @LOCAL
    def recover(self):
        """
        unpack → cover
        """
        self.blink_led(*SHORT_BLINK)
        if self.debug:
            print("[  MO-INFO  ] Recovery is going to be activated !")
            time.sleep(5)
            print("[  MO-INFO  ] <FAKE> RECOVERY ACTIVATED .")
        else:
            print("[  MO-INFO  ] PRODUCT RECOVERING ...")
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
                print("[  MO-INFO  ] PRODUCT RECOVERED .")
                self.blink_led(*LONG_BLINK)
                self.revive()
            except Exception as E:
                errors.append(E)
            
            if errors:
                print("[  MO-INFO  ] PRODUCT FAILED RECOVERED : %s" % "\n\t".join(errors))
                self.blink_led(*SHORT_BLINK)

    # @LOCAL
    def verify(self, unzipped_pkg, version_info):
        files_md5_comb = "".join(list(map(lambda x: md5_from_file(os.path.join(unzipped_pkg, x)), self.config.get("verifying_files"))))
        if version_info.get("md5") == md5_from_string(files_md5_comb):
            return True
        else:
            raise Exception("MD5 not matched")

    # @LOCAL
    def start_update_progress(self):
        threading.Thread(target=self._update_progress, args=()).start()

    # @LOCAL
    def _update_progress(self, interval=1):
        print("[  MO-INFO  ] Progress on . @%s" % (self.update_progress,))
        interval = max(0.5, interval)
        
        def report_progress():
            try:
                self.client.progress(*self.update_progress)
            except:
                pass

        while (self.update_progress[0] != 100):  # 未到 100%，则持续进度
            report_progress()
            if self.update_progress[2] != 0:  # 无异常
                time.sleep(interval)  # 则继续
            else:
                break
        
        report_progress()  # 报告最后一条进度
        print("[  MO-INFO  ] Progress off . @%s" % (self.update_progress,))

    # @LOCAL
    def try_notify(self, timeout=0, number_of_try=0, interval=1, args=(), success_key="", tips="..."):
        respond = Respond()
        notify = threading.Thread(target=self.notify, args=(*args, respond))
        notify.start()
        notify.join(timeout=timeout)

        if respond.payload == success_key:
            return success_key
        
        remain_times = ("REMIANED %s" % number_of_try) if number_of_try else ""
        print("[  MO-INFO  ] %s . TRYING ... %s" % (tips, remain_times))
            
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
        
        return respond.payload

    # @LOCAL
    def _ping(self, respond):
        try:
            respond.payload = self.client.ping()
        except:
            respond.payload = None

if __name__ == '__main__':

    config = {}

    # try:
    #     uri = sys.argv[1]
    # except:
    #     uri = "http://127.0.0.1:8282/"

    # try:
    #     local_rpc_port = sys.argv[2]
    # except:
    #     local_rpc_port = 8181

    try:
        debug = sys.argv[1]
        debug = False if (debug == "false" or debug == "False") else True
    except:
        debug = False

    # config["rpc_server"] = uri
    # config["port"] = local_rpc_port
    config["debug"] = debug

    Monitor(config).start()