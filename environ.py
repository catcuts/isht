# -*- coding: utf-8 -*-

# USERPASSWD = 0
# USERDATA = 1

# # notice codes from master process
# # MASTER_READY_FOR_UPDATE = 0
# MASTER_READY_FOR_UPDATE = True
# MASTER_RESTARTED = True
# MASTER_RESETTED = True

# MASTER_PROCESS_STARTED = 0
# UPDATE_READY_FOR_DOWNLOAD = 1
# DISCOVER_MODE_ACTIVATED = True
# DISCOVER_MODE_DEACTIVATED = False
# MASTER_PROCESS_ERROR = 4
# CANCEL_UPDATE = 5

# # nocice codes to master process
# UPDATE_PACKAGE_DOWNLOADED = 1
# INSUFFICIENT_MEMORY = 2
# INSUFFICIENT_SPACE = 3

# # led blink pattern
# LED_WAITING_TIME = 1.5  # waiting time should longer than all below
# ALWAYS_ON = (0, 0)
# LONG_BLINK = (0.2, 1.2)
# SHORT_BLINK = (0.2, 0.2)
# HIGH_FREQ_BLINK = (0.05, 0.05)

# # notify timeout
# NOTIFY_NUMBER_OF_TRY = 5  # 次
# NOTIFY_TIMEOUT = 5  # 秒

# # ping timeout
# PING_MAX_FAIL_TIMES = 2  # 次
# PING_INTERVAL = 20  # 秒
# PING_TIMEOUT = 0.5  # 秒

# # download timeout
# DOWNLOAD_TIMEOUT = 20

# # kill waiting time
# KILLING_WAITING_TIME = 5

# # request for updating
# UPDATING_ACCEPTED = 0
# UPDATING_REFUSED = 1
# CANCELLING_ACCEPTED = 0
# CANCELLING_REFUSED = 1

# # progress
# PROGRESS_DELAY = 0.6
# REPORT_PROGRESS_INTERVAL = 0.5

# # led pattern
# # depending on wiring
# # for example, one may wire the led which will be lighened by gpio.LOW
# # while for internal STATUS_LED, this is reversed
# DARK = 0
# LIGHT = 1