from .abstract import Rewriter
import logging
import tornado.ioloop
import sys
from datetime import datetime, timedelta


try:
    from scapy.all import IP, UDP, DNS
except ImportError:
    logging.error("Cannot import scapy. It's required for NameserverRewriter.")
    sys.exit(1)


DNS_TIMEOUT = 60
DNS_TIMEOUT_CLEARANCE = 10


class NameserverRewriter(Rewriter):
    def __init__(self, config):
        super(NameserverRewriter, self).__init__(config)
        self.logger = logging.getLogger(str(self))
        self.logger.debug("created.")
        self.records = {}
        self.periodic_callback = tornado.ioloop.PeriodicCallback(self.clear_timeout,
            DNS_TIMEOUT_CLEARANCE * 1000)
        if "force_nameserver" not in self.config:
            self.config['force_nameserver'] = '8.8.8.8'
            self.logger.warning("Using default nameserver " + self.config['force_nameserver'])

    def __str__(self):
        return "nameserver-rewriter(%s)" % self.config.get("force_nameserver", 'Unknown')

    def rewrite(self, pkt):
        ip = IP(pkt)
        if ip.haslayer(DNS):
            dns = ip.getlayer(DNS)
            if dns.qr == 0:  # query
                record = {
                    'dst_ip':  ip.dst,
                    'time': datetime.utcnow()
                }
                self.records[dns.id] = record
                self.logger.debug("rewriting DNS query: %s to %s" % (ip.dst,
                    self.config['force_nameserver']))
                ip.dst = self.config['force_nameserver']
                return str(ip)
            elif dns.qr == 1:  # answer
                self.logger.debug("found DNS answer: " + dns.summary())
                record = self.records.get(dns.id, None)
                if record:
                    self.logger.debug("rewriting DNS answer: %s to %s" % (ip.src,
                        record['dst_ip']))
                    ip.src = record['dst_ip']
                    del self.records[dns.id]
                    return str(ip)
        return pkt

    def clear_timeout(self):
        for dns_id in self.records:
            record = self.records[dns_id]
            if (record['time'] - datetime.utcnow()) > timedelta(seconds=DNS_TIMEOUT):
                del self.records[dns_id]

    def cleanup(self):
        self.periodic_callback.stop()

    def setup(self):
        self.periodic_callback.start()
