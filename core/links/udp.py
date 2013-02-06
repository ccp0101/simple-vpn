from .abstract import Link
from ..networking.packet import Packet
from ..utils import validate_port, Error, read_packet
import struct
import tornado.gen
import logging
import socket
import tornado.netutil
import tornado.ioloop
from datetime import timedelta, datetime
import json


UDP_MAGIC_WORD = 0x1306A15
UDP_BUF_SIZE = 2048
IDENTIFIER_LENGTH = 4
RESET_PACKET = struct.pack("!B", 0x00)
CONTROL_MESSAGE_IDENTIFIER = 0x01
PACKET_IDENTIFIER = 0x02
KEEP_ALIVE_IDENTIFIER = 0x03
KEEP_ALIVE_SECONDS = 30
CHECK_SECONDS = 30
CONNECTION_DEATH_SECONDS = 90


class UDPLink(Link):
    MAGIC_WORD = 0x1306A15

    @classmethod
    def get_manager_class(cls, mode):
        if mode == "server":
            return UDPLinkServerManager
        elif mode == "client":
            return UDPLinkClientManager

    def __init__(self, manager, address):
        self.manager = manager
        self.dest = address
        self.logger = logging.getLogger(str(self))
        self.logger.debug("created.")
        self.periodic_check = tornado.ioloop.PeriodicCallback(self.check_alive,
            CHECK_SECONDS * 1000)
        self.periodic_send_alive = tornado.ioloop.PeriodicCallback(
            self.send_alive, KEEP_ALIVE_SECONDS * 1000)
        self.record_alive()

    def __str__(self):
        if not hasattr(self, "_name"):
            self._name = u"udplink<%s:%d>" % (self.dest)
        return self._name

    @property
    def ip_endpoint(self):
        return self.dest[0]

    def check_alive(self):
        if datetime.utcnow() - self.last_recorded > timedelta(
            seconds=CONNECTION_DEATH_SECONDS):
            self.manager.write(RESET_PACKET, self.dest)
            self.apply_close_callback()

    def send_alive(self):
        self.manager.write(struct.pack("!B", KEEP_ALIVE_IDENTIFIER), self.dest)
        self.logger.debug("sent keep-alive")

    def setup(self):
        self.periodic_check_alive.start()
        self.periodic_send_alive.start()

    def parse_packet(self, pkt):
        payload = pkt.payload
        consumed = 0

        if payload == RESET_PACKET:
            self.logger.info("received RESET")
            self.apply_close_callback()
        else:
            if len(payload) >= 3:
                type_byte, = struct.unpack("!B", payload[consumed:
                    consumed + 1])
                consumed += 1
                if type_byte not in [CONTROL_MESSAGE_IDENTIFIER,
                    PACKET_IDENTIFIER, KEEP_ALIVE_IDENTIFIER]:
                    self.manager.write(RESET_PACKET, self.dest)
                length, = struct.unpack("!H", payload[consumed:
                    consumed + 2])
                consumed += 2

                if len(payload) >= (consumed + length):
                    data = payload[consumed: consumed + length]
                    if type_byte == CONTROL_MESSAGE_IDENTIFIER:
                        try:
                            msg = json.loads(data)
                        except:
                            raise
                            self.logger.error("cannot parse message: " + data)
                            return
                        self.logger.debug("received message: " + str(msg))
                        self.record_alive()
                        self.apply_message_callback(msg)
                    elif type_byte == PACKET_IDENTIFIER:
                        self.record_alive()
                        p = Packet(data, source=self)
                        self.logger.debug("received: " + str(p))
                        self.apply_packet_callback(p)
                    elif type_byte == KEEP_ALIVE_IDENTIFIER:
                        self.logger.debug("received keep-alive")
                        self.record_alive()

    def record_alive(self):
        self.last_recorded = datetime.utcnow()

    def establish(self, callback):
        callback()

    def cleanup(self):
        self.periodic_check.stop()
        self.periodic_send_alive.stop()
        try:
            self.manager.write(RESET_PACKET, self.dest)
        except:
            pass

    def is_alive(self):
        return True

    def send_packet(self, packet):
        data = struct.pack("!B", PACKET_IDENTIFIER) + packet.serialize()
        self.manager.write(data, self.dest)
        self.logger.debug("sent: %s" % str(packet))

    def send_message(self, msg):
        serialized = bytes(json.dumps(msg))
        self.manager.write(struct.pack("!BH", CONTROL_MESSAGE_IDENTIFIER,
            len(serialized)) + serialized, self.dest)
        self.logger.debug("sent message: " + str(msg))


class UDPLinkClientManager(object):
    def __init__(self, config):
        self.config = config
        self.io_loop = tornado.ioloop.IOLoop.instance()
        self.logger = logging.getLogger(str(self))
        self.logger.debug("created.")

    def __str__(self):
        return "udp<%s:%d>" % (self.config['host'], self.config['port'])

    def setup(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    def cleanup(self):
        self.io_loop.remove_handler(self.socket)

    @tornado.gen.engine
    def create(self, callback):
        addr = (self.config['host'], self.config['port'])

        self.socket.sendto(struct.pack("!L", UDP_MAGIC_WORD), addr)

        self.logger.info("sent initialial message.")
        data, peer = yield tornado.gen.Task(read_packet, self.socket)
        if data == RESET_PACKET:
            callback(None)
            return

        if len(data) == struct.calcsize("!L"):
            word, = struct.unpack("!L", data)
            if word == UDP_MAGIC_WORD:
                self.logger.info("received correct magic word.")
                self.link = UDPLink(self, peer)
                self.io_loop.add_handler(self.socket, self.on_socket_read,
                    self.io_loop.READ)
                callback(self.link)
            else:
                self.logger.info("received incorrect magic word: 0x%X" % word)
                self.socket.sendto(RESET_PACKET, peer)
                callback(None)
        else:
            self.logger.info("received packet of wrong size.")
            self.socket.sendto(RESET_PACKET, peer)
            callback(None)

    def on_socket_read(self, fd, events):
        data, addr = self.socket.recvfrom(UDP_BUF_SIZE)
        self.link.parse_packet(Packet(data, source=self, routing={
            'src': addr
            }))

    def write(self, data, addr):
        self.socket.sendto(data, addr)


class UDPLinkServerManager(object):
    def __init__(self, config):
        self.config = config
        self.creation_callback = None
        self.io_loop = tornado.ioloop.IOLoop.instance()
        self.addr_links = {}
        self.logger = logging.getLogger(str(self))
        self.logger.debug("created.")

    def __str__(self):
        return "udp-manager<%d>" % self.config['port']

    def setup(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(('0.0.0.0', self.config['port']))
        self.logger.info("listening for UDP packets on port %d" %
            self.config['port'])
        self.io_loop.add_handler(self.socket.fileno(), self.on_socket_read,
            self.io_loop.READ)

    def on_socket_read(self, fd, events):
        data, addr = self.socket.recvfrom(UDP_BUF_SIZE)

        link = self.addr_links.get(addr, None)
        if link is None:
            magic_word, = struct.unpack("!L", data)
            if magic_word != UDP_MAGIC_WORD:
                self.logger.debug("magic word does not match.")
                self.socket.sendto(RESET_PACKET, addr)
            else:
                if data == RESET_PACKET:
                    return
                link = UDPLink(self, addr)
                self.addr_links[addr] = link
                self.socket.sendto(struct.pack("!L", UDP_MAGIC_WORD), addr)
                self.logger.info("new client from " + str(addr))
                self.creation_callback(link)
        else:
            pkt = Packet(data, source=self, routing={
                'src': addr
                })
            link.parse_packet(pkt)

    def write(self, data, addr):
        self.socket.sendto(data, addr)

    def create(self, callback):
        self.creation_callback = callback

    def cleanup(self):
        self.io_loop.remove_handler(self.socket.fileno())
