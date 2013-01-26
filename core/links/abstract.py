import abc
import tornado.ioloop
import logging
from ..utils import Error


class Link(object):
    __metaclass__ = abc.ABCMeta

    def setup(self):
        pass

    def cleanup(self):
        pass

    def is_alive(self):
        return True

    @abc.abstractmethod
    def send_packet(self, packet):
        pass

    def set_packet_callback(self, callback):
        self.packet_callback = callback

    def apply_packet_callback(self, packet):
        func = getattr(self, "packet_callback", None)
        if func:
            func(packet)

    def set_close_callback(self, callback):
        self.close_callback = callback

    def apply_close_callback(self):
        func = getattr(self, "close_callback", None)
        if func:
            func()
            # call only once
            self.close_callback = None
