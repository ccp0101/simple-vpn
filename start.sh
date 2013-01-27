#!/bin/bash

/sbin/ifconfig tun0 10.4.0.6 10.4.0.5 mtu 1500 netmask 255.255.255.255 up
/sbin/route add -net 10.4.0.0 10.4.0.5  255.255.255.0
/sbin/route add -net 173.212.221.150 10.4.0.5 255.255.255.255
