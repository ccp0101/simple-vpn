from . import ipaddr


class IPAddressSpaceManager(object):
    def __init__(self, definition):
        self.definition = definition
        self.network = ipaddr.ip_network(self.definition)
        self.hosts = list(self.network.iterhosts())
        self.addons = []

    @classmethod
    def shared(cls, definition):
        attr_name = "_shared_instance"
        if not cls.hasattr(attr_name):
            instance = IPAddressSpaceManager(definition)
            setattr(cls, attr_name, instance)
        return getattr(cls, attr_name)

    def allocate(self):
        try:
            return self.hosts.pop(0).exploded
        except IndexError:
            return None

    def release(self, host):
        self.hosts.append(host)
