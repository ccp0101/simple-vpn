sudo ifconfig tun0 10.4.0.5 pointopoint 10.4.0.6 up

sudo /sbin/ifconfig tun0 10.4.0.6 10.4.0.5 mtu 1500 netmask 255.255.255.255 up
sudo /sbin/ifconfig tun1 10.4.0.5 10.4.0.6 mtu 1500 netmask 255.255.255.255 up
