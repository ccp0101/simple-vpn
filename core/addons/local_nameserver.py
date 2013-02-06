from .abstract import Addon
import socket
import logging
import tornado.ioloop
import tornado.gen
from datetime import datetime, timedelta


try:
    from scapy.all import DNS
except ImportError:
    logging.error("Cannot import scapy. LocalNameserver requires scapy.")
    raise


class LocalNameserver(Addon):
    def setup(self):
        self.remote = self.config.get('remote', '8.8.8.8')
        self.logger = logging.getLogger("local-nameserver<%s>" % self.remote)
        self.io_loop = tornado.ioloop.IOLoop.instance()
        self.records = {}
        self.socket = None
        self.periodic = tornado.ioloop.PeriodicCallback(self.timeout, 5000)
        self.periodic.start()

    def cleanup(self):
        self.periodic.stop()
        if self.socket:
            self.io_loop.remove_handler(self.socket.fileno())
            self.socket.close()

    @tornado.gen.engine
    def on_session_established(self):
        yield tornado.gen.Task(self.io_loop.add_callback)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind((self.config.get('host', '127.0.0.1'),
            self.config.get('port', 53)))
        self.io_loop.add_handler(self.socket.fileno(),
            self.on_read, self.io_loop.READ)

    def on_read(self, fd, events):
        data, addr = self.socket.recvfrom(2048)
        try:
            dns = DNS(data)
        except:
            self.logger.warning("received malformed DNS packet from " + str(addr))
            return

        if dns.qr == 0:
            self.records[str(dns.id)] = {'time': datetime.utcnow(), 'from': addr}
            try:
                self.socket.sendto(data, (self.remote, 53))
                self.logger.debug("forwarded DNS request from " + str(addr))
            except Exception as e:
                self.logger.error(str(e))
        elif dns.qr == 1:
            record = self.records.get(str(dns.id), None)
            if record:
                try:
                    self.socket.sendto(data, record['from'])
                    self.logger.debug("forwarded DNS answer to " + str(record['from']))
                except Exception as e:
                    self.logger.error(str(e))
                del self.records[str(dns.id)]
            else:
                self.logger.debug("unknown DNS answer: " + dns.summary())

    def timeout(self):
        for dns_id in self.records:
            record = self.records[dns_id]
            if datetime.utcnow() - record['time'] > timedelta(seconds=60):
                del self.records[dns_id]
