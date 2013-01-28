from .abstract import Device, DeviceManager
from ..networking.packet import Packet
from fcntl import ioctl
from ..utils import Error, hexdump, run_os_command, get_default_route
import struct
import tornado.ioloop
import logging
import sys
import os.path
import functools


class TUNDevice(Device):
    TUNSETIFF = 0x400454ca
    IFF_TUN = 0x0001
    IFF_TAP = 0x0002
    IFF_NO_PI = 0x1000
    MAX_BUF_SIZE = 2048
    IFNAME_PREFIX = "vpn"

    def __init__(self, io_loop=None):
        self.io_loop = io_loop or tornado.ioloop.IOLoop.instance()
        self.callback = None
        self.fd = None
        self.ifname = None
        self.added_routes = []
        self.setup_logger()
        self.logger.debug("created.")

    def setup_logger(self):
        self.logger = logging.getLogger(str(self))

    def __str__(self):
        return "ifname<%s>" % self.ifname if self.ifname else "tun"

    def open_tun(self, path):
        mode = self.IFF_TUN | self.IFF_NO_PI
        tun = os.open(path, os.O_RDWR)
        if "linux" in sys.platform:
            ifs = ioctl(tun, self.TUNSETIFF, struct.pack("16sH", self.IFNAME_PREFIX + "%d", mode))
            ifname = ifs[:16].strip("\x00")
        elif "darwin" in sys.platform:
            ifname = os.path.split(path)[-1]
        return (tun, ifname)

    def setup(self):
        opened_path = None
        if "darwin" in sys.platform:
            for i in range(0, 16):
                path = "/dev/tun" + str(i)
                self.logger.debug("trying to open " + path)
                try:
                    self.fd, self.ifname = self.open_tun(path)
                    opened_path = path
                    break
                except OSError as e:
                    self.logger.debug(str(e))
        else:
            path = "/dev/net/tun"
            self.logger.debug("trying to open " + path)
            try:
                self.fd, self.ifname = self.open_tun(path)
                opened_path = path
            except OSError as e:
                self.logger.debug(str(e))
        if opened_path:
            self.setup_logger()
            """
            Hack Tornado so that ERROR event is not automatically added, equal to:

                self.io_loop._handlers[self.fd.fileno()] = self.on_read
                self.io_loop._impl.register(self.fd.fileno(), self.io_loop.READ)
            """
            self.logger.info("opened " + opened_path)
            error_event = self.io_loop.ERROR
            self.io_loop.ERROR = 0
            self.io_loop.add_handler(self.fd, self.on_read, self.io_loop.READ)
            self.io_loop.ERROR = error_event
        else:
            self.fd = None
            raise Error("cannot open tun device.")

    def cleanup(self):
        if self.fd:
            self.logger.info("closing tun device.")
            self.io_loop.remove_handler(self.fd)
            os.close(self.fd)
        self.fd = None

    def on_read(self, fd, events):
        payload = os.read(self.fd, self.MAX_BUF_SIZE)
        p = Packet(payload, source=self)
        self.logger.debug("read: %s" % str(p))
        self.apply_packet_callback(p)

    def send_packet(self, pkt):
        os.write(self.fd, pkt.payload)
        self.logger.debug("wrote: %s" % str(pkt))

    def interface_up(self, *args):
        if "darwin" in sys.platform:
            run_os_command("/sbin/ifconfig %s %s %s mtu 1500 netmask 255.255.255.255 up" % args)
        else:
            run_os_command("/sbin/ifconfig %s %s pointtopoint %s up" % args)

    def interface_down(self, ifname):
        run_os_command("/sbin/ifconfig %s down" % ifname)

    def modify_route(self, network, netmask, gateway_ip, gateway_ifname, operation="add"):
        if "darwin" in sys.platform:
            run_os_command("/sbin/route %s -net %s %s %s" (operation, network, gateway_ip, netmask))
        else:
            run_os_command("/sbin/route %s -net %s netmask %s gw %s dev %s" %
                (operation, network, netmask, gateway_ip, gateway_ifname))

    def add_route(self, *args):
        self.modify_route(*args, operation="add")
        self.added_routes.append(args)

    def restore_routes(self):
        for route in self.added_routes:
            self.modify_route(*route, operation="del")
        self.added_routes = []

    def configure_network(self, server_public_ip, server_private_ip=None, client_private_ip=None,
            add_routes=False):
        self.interface_up(self.ifname, client_private_ip, server_private_ip)
        if add_routes:
            self.gw_ip, self.gw_ifname = get_default_route()
            self.add_route(server_public_ip, '255.255.255.255', self.gw_ip, self.gw_ifname)
            self.add_route('0.0.0.0', '128.0.0.0', server_private_ip, client_private_ip)
            self.add_route('128.0.0.0', '128.0.0.0', server_private_ip, client_private_ip)

    def restore_network(self, server_public_ip, server_private_ip=None, client_private_ip=None):
        self.interface_down(self.ifname)
        self.restore_routes()


class TUNDeviceManager(DeviceManager):
    def create(self, callback):
        callback(TUNDevice())
