import struct


class Packet(object):
    def __init__(self, payload=None, source=None, routing={}):
        self.payload = payload
        self.source = source
        self.routing = routing

    def serialize(self):
        ret = struct.pack("!H", len(self.payload))
        ret += self.payload
        return ret

    def __str__(self):
        name = "Packet of %d bytes" % len(self.payload)
        if self.source:
            name += " from %s" % str(self.source)
        return name
