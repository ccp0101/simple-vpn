simple-vpn
==========

sudo ipfw add 100 divert 20123 ip from me to 173.212.221.150

sudo ipfw del 100

sudo ifconfig tun0 192.168.7.1 192.168.7.2 up
sudo route -n add 173.212.221.150/32  192.168.7.2

route -n delete -net 173.212.221.150/32

2013-01-26 13:06:42 /sbin/ifconfig tun0 10.4.0.6 10.4.0.5 mtu 1500 netmask 255.255.255.255 up


2013-01-26 13:06:45 /sbin/route add -net 184.82.229.13 10.0.2.1 255.255.255.255
                                        add net 184.82.229.13: gateway 10.0.2.1
2013-01-26 13:06:45 /sbin/route add -net 0.0.0.0 10.4.0.5 128.0.0.0
                                        add net 0.0.0.0: gateway 10.4.0.5
2013-01-26 13:06:45 /sbin/route add -net 128.0.0.0 10.4.0.5 128.0.0.0
                                        add net 128.0.0.0: gateway 10.4.0.5
2013-01-26 13:06:45 MANAGEMENT: >STATE:1359176805,ADD_ROUTES,,,
2013-01-26 13:06:45 /sbin/route add -net 10.4.0.0 10.4.0.5 255.255.255.0
                                        add net 10.4.0.0: gateway 10.4.0.5


2013-01-26 13:06:48 /sbin/route delete -net 10.4.0.0 10.4.0.5 255.255.255.0
                                        delete net 10.4.0.0: gateway 10.4.0.5
2013-01-26 13:06:48 /sbin/route delete -net 184.82.229.13 10.0.2.1 255.255.255.255
                                        delete net 184.82.229.13: gateway 10.0.2.1
2013-01-26 13:06:48 /sbin/route delete -net 0.0.0.0 10.4.0.5 128.0.0.0
                                        delete net 0.0.0.0: gateway 10.4.0.5
2013-01-26 13:06:48 /sbin/route delete -net 128.0.0.0 10.4.0.5 128.0.0.0
                                        delete net 128.0.0.0: gateway 10.4.0.5
2013-01-26 13:06:48 Closing TUN/TAP interface
2013-01-26 13:06:48 /Applications/Tunnelblick.app/Contents/Resources/client.down.tunnelblick.sh -m -w -d -atADGNWradsgnw tun0 1500 1544 10.4.0.6 10.4.0.5 init
                                          No such key

sudo /sbin/ifconfig tun0 10.4.0.6 10.4.0.5 mtu 1500 netmask 255.255.255.255 up
sudo /sbin/route add -net 173.212.221.150 10.4.0.5 255.255.255.255

/sbin/ifconfig tun0 10.4.0.1 pointopoint 10.4.0.2 mtu 1500

echo 1 > /proc/sys/net/ipv4/ip_forward
