# -*- coding: utf-8 -*-

import os
import sys
import time
from itertools import cycle

if not os.getegid() == 0:
    sys.exit('Script must be run as root')

from pyA20.gpio import gpio
from pyA20.gpio import connector
from pyA20.gpio import port

led = port.STATUS_LED

gpio.init()
gpio.setcfg(led, gpio.OUTPUT)

def blink_led(interval=0):
    try:
        value = gpio.HIGH
        gpio.output(led, value)
        if interval:
            zerone = cycle((gpio.LOW, gpio.HIGH))
            while True:
                print("value = %s" % value)
                time.sleep(interval)
                value = next(zerone)
                gpio.output(led, value)
    except KeyboardInterrupt:
        print("Goodbye.")

blink_led(1.2)
