import abc
import logging
import tornado.ioloop
from ..utils import Error


class Device(object):
    __metaclass__ = abc.ABCMeta

    def setup(self):
        pass

    def cleanup(self):
        pass

    def is_alive(self):
        return True

    def set_packet_callback(self, callback):
        self.packet_callback = callback

    def apply_packet_callback(self, packet):
        func = getattr(self, "packet_callback", None)
        if func:
            func(packet)


class DeviceManager(object):
    __metaclass__ = abc.ABCMeta

    def __init__(self, config):
        self.config = config

    def setup(self):
        pass

    def cleanup(self):
        pass
