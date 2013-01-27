from .abstract import Link
from ..networking.packet import Packet
from tornado.iostream import IOStream
from ..utils import validate_port, Error
import struct
import tornado.gen
import logging
import socket
import tornado.netutil
import tornado.ioloop
import functools
from datetime import timedelta
from collections import deque


class TCPLink(Link):
    MAGIC_WORD = 0x1306A15

    def __init__(self, stream):
        self.stream = stream
        self.io_loop = tornado.ioloop.IOLoop.instance()
        self.dest = self.stream.socket.getpeername()
        self.connected = True
        self.logger = logging.getLogger(str(self))
        self.logger.debug("created.")

    def __str__(self):
        if not hasattr(self, "_name"):
            self._name = u"tcplink<%s:%d>" % (self.dest)
        return self._name

    def setup(self):
        self.send_magic_word()

    @tornado.gen.engine
    def establish(self, callback):
        self.logger.debug("establishing session link.")

        # add a close timeout in case server does not respond
        handle = self.io_loop.add_timeout(timedelta(seconds=5), self.apply_close_callback)
        data = yield tornado.gen.Task(self.stream.read_bytes, 4)
        self.io_loop.remove_timeout(handle)

        word, = struct.unpack("!L", data)
        if word != self.MAGIC_WORD:
            self.logger.debug("received wrong magic word: 0x%X" % word)
            self.stream.close()
        else:
            self.stream.set_close_callback(self.on_close)
            self.logger.debug("received correct magic word: 0x%X" % word)
            callback()
            self.io_loop.add_callback(self.wait_packet)

    def cleanup(self):
        self.callback = None
        self.stream.close()

    def is_alive(self):
        return self.connected

    def send_packet(self, packet):
        self.stream.write(packet.serialize())
        self.logger.debug("sent: %s" % str(packet))

    def on_close(self):
        self.connected = False
        if self.stream.error:
            logging.error("error in connection to (%s:%d): " % self.dest +
                str(self.stream.error))
        self.apply_close_callback()

    def send_magic_word(self):
        self.stream.write(struct.pack("!L", self.MAGIC_WORD))
        self.logger.debug("sent magic word: 0x%X" % self.MAGIC_WORD)

    @tornado.gen.engine
    def wait_packet(self):
        data = yield tornado.gen.Task(self.stream.read_bytes, struct.calcsize("!H"))
        length, = struct.unpack("!H", data)
        payload = yield tornado.gen.Task(self.stream.read_bytes, length)
        pkt = Packet(payload, source=self)
        self.logger.debug("received: " + str(pkt))
        self.apply_packet_callback(pkt)
        self.io_loop.add_callback(self.wait_packet)


class TCPLinkClientManager(object):
    def __init__(self, config):
        self.config = config
        self.stream = None
        self.creation_callback = None

    def setup(self):
        pass

    def create(self, callback):
        self.creation_callback = callback
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        self.stream = IOStream(s)
        self.stream.set_close_callback(self.on_close)
        self.stream.connect((self.config['host'], self.config['port']), self.on_connect)

    @tornado.gen.engine
    def on_connect(self):
        if self.stream:
            if self.creation_callback:
                link = TCPLink(self.stream)
                link.setup()
                yield tornado.gen.Task(link.establish)
                self.creation_callback(link)
                self.creation_callback = None
        self.stream = None

    def on_close(self):
        if self.stream:
            self.stream.set_close_callback(None)
            if self.stream.error:
                logging.error(self.stream.error)
            if self.creation_callback:
                self.creation_callback(None)
                self.creation_callback = None
        self.stream = None

    def cleanup(self):
        self.stream = None


class TCPLinkServerManager(object):
    def __init__(self, config):
        self.config = config
        self.creation_callback = None

    def setup(self):
        class Server(tornado.netutil.TCPServer):
            def __init__(self, bind_address):
                super(Server, self).__init__()
                self.established = deque([])
                self.bind_address = bind_address
                self.callback = None

            def bind(self):
                super(Server, self).bind(self.bind_address[1], address=self.bind_address[0])
                self.start(1)
                logging.debug("started tcp server on (%s:%d)" % self.bind_address)

            def handle_stream(self, stream, address):
                logging.debug("new stream from " + str(address))
                link = TCPLink(stream)
                link.setup()
                link.establish(functools.partial(self.on_established, link))

            def on_established(self, link):
                logging.debug("%s established" % str(link))
                if self.callback:
                    self.callback(link)
                    self.callback = None
                else:
                    self.established.append(link)

            def get_link(self, callback):
                try:
                    s = self.established.popleft()
                except IndexError:
                    self.callback = callback
                    return
                callback(s)

        self.server = Server(('0.0.0.0', self.config['port']))
        self.server.bind()

    @tornado.gen.engine
    def create(self, callback):
        s = yield tornado.gen.Task(self.server.get_link)
        callback(s)

    def cleanup(self):
        self.server.stop()
