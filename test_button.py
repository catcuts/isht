
# -*- coding: utf-8 -*-

import os
import sys
import time

if not os.getegid() == 0:
    sys.exit('Script must be run as root')

from pyA20.gpio import gpio
from pyA20.gpio import connector
from pyA20.gpio import port


reset_button = port.PA9
set_button = port.PA10
led = port.PG6

# Init gpio module
gpio.init()

# Set directions
gpio.setcfg(reset_button, gpio.INPUT)
gpio.setcfg(set_button, gpio.INPUT)
gpio.setcfg(led, gpio.OUTPUT)

try:
    print ("Press CTRL+C to exit")
    while True:
        reset_state = gpio.input(reset_button)
        set_state = gpio.input(set_button)
        # gpio.output(led, not state)
        print("\nState:\n\n\tReset State: %s\n\tSet State: %s" % (reset_state, set_state))
        time.sleep(1)

except KeyboardInterrupt:
    print ("Goodbye.")

