from .abstract import Device, DeviceManager
from ..networking.packet import Packet
from fcntl import ioctl
from ..utils import Error
import struct
import tornado.ioloop
import logging
import sys
import os.path


class TUNDevice(Device):
    TUNSETIFF = 0x400454ca
    IFF_TUN = 0x0001
    IFF_TAP = 0x0002
    IFF_NO_PI = 0x1000
    MAX_BUF_SIZE = 2048
    IFNAME_PREFIX = "tun"

    def __init__(self, io_loop=None):
        self.io_loop = io_loop or tornado.ioloop.IOLoop.instance()
        self.callback = None
        self.fd = None
        self.logger = logging.getLogger(str(self))
        self.logger.debug("created.")

    def __str__(self):
        return "tun"

    def open_tun(self, path):
        mode = self.IFF_TUN | self.IFF_NO_PI
        tun = open(path, "rw")
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
                except IOError as e:
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
            """
            Hack Tornado so that ERROR event is not automatically added, equal to:

                self.io_loop._handlers[self.fd.fileno()] = self.on_read 
                self.io_loop._impl.register(self.fd.fileno(), self.io_loop.READ)
            """
            self.logger.info("opened " + opened_path)
            error_event = self.io_loop.ERROR
            self.io_loop.ERROR = 0
            self.io_loop.add_handler(self.fd.fileno(), self.on_read, self.io_loop.READ)
            self.io_loop.ERROR = error_event
        else:
            self.fd = None
            raise Error("cannot open tun device.")

    def cleanup(self):
        if self.fd:
            self.logger.info("closing tun device.")
            self.io_loop.remove_handler(self.fd.fileno())
            self.fd.close()
        self.fd = None

    def on_read(self, fd, events):
        payload = self.fd.read(self.MAX_BUF_SIZE)
        p = Packet(payload, source=self)
        self.logger.debug("read: %s" % str(p))
        self.apply_packet_callback(p)

    def send_packet(self, pkt):
        self.fd.write(pkt.payload)
        self.logger.debug("wrote: %s" % str(pkt))


class TUNDeviceManager(DeviceManager):
    def create(self, callback):
        callback(TUNDevice())
