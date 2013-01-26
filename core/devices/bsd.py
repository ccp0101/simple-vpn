from .abstract import Device, DeviceManager
from ..networking.packet import Packet
from ..utils import validate_port, Error
import socket
import logging
import tornado.ioloop


class DivertSocketDevice(Device):
    IPPROTO_DIVERT = socket.getprotobyname("divert")
    MAX_BUF_SIZE = 2048

    def __init__(self, port, io_loop=None):
        self.io_loop = io_loop or tornado.ioloop.IOLoop.instance()
        self.port = port
        self.callback = None
        self.logger = logging.getLogger(str(self))
        self.logger.debug("created.")

    def __str__(self):
        return u"divert<%d>" % self.port

    def setup(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, self.IPPROTO_DIVERT)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", self.port))
        self.sock.setblocking(0)
        self.source_name = "divert:%d" % self.port
        self.io_loop.add_handler(self.sock.fileno(), self.on_read, self.io_loop.READ)

    def on_read(self, fd, events):
        payload, addr = self.sock.recvfrom(self.MAX_BUF_SIZE)
        if addr[0] == "0.0.0.0":
            """
            IP address set to the (first) address of the interface
            on which the packet was received (if the packet was
            incoming) or INADDR_ANY (if the packet was outgoing)
            """
            direction = "outgoing"
        else:
            direction = "incoming"
        p = Packet(payload, source=self.source_name, routing={'addr': addr,
            'direction': direction})
        self.logger.debug("received: %s" % str(p))
        self.apply_packet_callback(p)

    def cleanup(self):
        self.io_loop.remove_handler(self.sock.fileno())
        self.sock.close()

    def send_packet(self, pkt):
        self.sock.send(pkt.payload)


class DivertSocketDeviceManager(DeviceManager):
    def create(self, callback):
        callback(DivertSocketDevice(self.config['port']))
