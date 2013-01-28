from .abstract import Device, DeviceManager
from ..networking.packet import Packet
from ..utils import validate_port, Error, run_os_command
import socket
import logging
import sys
import tornado.ioloop


class DivertSocketDevice(Device):
    IPPROTO_DIVERT = socket.getprotobyname("divert")
    MAX_BUF_SIZE = 2048
    IPFW_RULE_PRIORITY = 1000

    def __init__(self, port, io_loop=None):
        if "darwin" not in sys.platform:
            raise Error("Divert socket works only on Mac OS X")
        self.io_loop = io_loop or tornado.ioloop.IOLoop.instance()
        self.port = port
        self.callback = None
        self.ipfw_modified = False
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
        self.source_ip = "127.0.0.1"

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
        self.source_ip = payload[12:16]
        self.logger.debug("received: %s" % str(p))
        self.apply_packet_callback(p)

    def cleanup(self):
        self.io_loop.remove_handler(self.sock.fileno())
        self.sock.close()

    def send_packet(self, pkt):
        payload = pkt.payload
        payload[16:20] = self.source_ip
        self.sock.send(payload)
        self.logger.debug("sent: %s" % str(pkt))

    def configure_network(self, server_public_ip, server_private_ip=None, client_private_ip=None,
            add_routes=False):
        if add_routes:
            run_os_command("/sbin/ipfw add %d accept ip from me to %s" %
                (self.IPFW_RULE_PRIORITY - 1, server_public_ip))
            run_os_command("/sbin/ipfw add %d accept ip from %s to me" %
                (self.IPFW_RULE_PRIORITY - 1, server_public_ip))
            run_os_command("/sbin/ipfw add %d divert %d ip from me to any" %
                (self.IPFW_RULE_PRIORITY, self.port))
            run_os_command("/sbin/ipfw add %d divert %d ip from any to me" %
                (self.IPFW_RULE_PRIORITY, self.port))
            self.ipfw_modified = True

    def restore_network(self, server_public_ip, server_private_ip=None, client_private_ip=None):
        if self.ipfw_modified:
            run_os_command("/sbin/ipfw del %d" % (self.IPFW_RULE_PRIORITY))
            run_os_command("/sbin/ipfw del %d" % (self.IPFW_RULE_PRIORITY - 1))


class DivertSocketDeviceManager(DeviceManager):
    def create(self, callback):
        callback(DivertSocketDevice(self.config['port']))
