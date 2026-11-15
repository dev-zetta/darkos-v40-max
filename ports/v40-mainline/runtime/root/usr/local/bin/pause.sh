#!/bin/bash
set -e
if [[ -e /home/ark/.config/.SWAPPOWERANDSUSPEND ]]; then
  exec sudo -n /usr/local/sbin/v40max-power-request poweroff
else
  exec sudo -n /usr/local/sbin/v40max-power-request suspend
fi
