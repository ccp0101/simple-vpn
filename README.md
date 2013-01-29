simple-vpn
==========

sudo /sbin/iptables -t nat -I POSTROUTING -s 10.48.0.0/24 -j MASQUERADE
echo 1 > /proc/sys/net/ipv4/ip_forward