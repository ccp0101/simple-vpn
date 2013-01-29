import abc


class Rewriter(object):
    __metaclass__ = abc.ABCMeta

    def __init__(self, config={}):
        self.config = config

    def setup(self):
        pass

    def cleanup(self):
        pass

    @abc.abstractmethod
    def rewrite(self, pkt):
        pass
