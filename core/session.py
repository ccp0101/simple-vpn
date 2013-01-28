import logging
import subprocess
import uuid
import functools
import ipaddr
from utils import run_os_command


class IPAddressSpaceManager(object):
    def __init__(self, definition):
        self.definition = definition
        self.network = ipaddr.ip_network(self.definition)
        self.hosts = list(self.network.iterhosts())

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


class Session(object):
    def __init__(self, mode, config, device, link, name=None):
        self.mode = mode
        self.config = config
        self.device = device
        self.name = name or uuid.uuid4().hex
        self.link = link
        self.logger = logging.getLogger("session[%s,%s]" % (str(self.device),
            str(self.link)))
        self.close_callback = None
        self.setup_callback = None
        self.network_configured = False
        self.logger.debug("created.")

    def setup(self, close_callback):
        real_callback = functools.partial(close_callback, self)
        self.link.set_close_callback(real_callback)
        self.device.setup()
        self.logger.info("device initiated!")
        self.link.set_message_callback(self.on_message)

        if self.mode == "server":
            self.ip_manager = IPAddressSpaceManager(self.config['network'])
        else:
            self.link.send_message({
                "type": "ip_request"
                })

    def on_message(self, msg):
        if msg.get("type") == "ip_request" and self.mode == "server":
            self.server_ip, self.client_ip = self.ip_manager.allocate(
                ), self.ip_manager.allocate()
            self.link.send_message({
                "type": "ip_reply",
                "server_ip": self.server_ip,
                "client_ip": self.client_ip,
                "network":  self.config['network']
                })
        elif msg.get("type") == "ip_confirm" and self.mode == "server":
            self.finalize_session()
        elif msg.get("type") == "ip_reply" and self.mode == "client":
            self.server_ip = msg["server_ip"]
            self.client_ip = msg["client_ip"]
            self.link.send_message({"type": "ip_confirm"})
            self.finalize_session()

    def configuration_parameters(self):
        return (self.link.ip_endpoint, self.server_ip, self.client_ip)

    def finalize_session(self):
        self.logger.debug("configuring network.")
        self.device.configure_network(*self.configuration_parameters(),
            add_routes=(self.mode == "client"))
        self.network_configured = True

        # hook = self.config.get("hooks", {}).get("start", None)
        # if hook:
        #     run_os_command(hook)
        self.device.set_packet_callback(self.on_device_packet)
        self.link.set_packet_callback(self.on_link_packet)
        self.logger.info("session initiated!")

    def on_device_packet(self, packet):
        self.link.send_packet(packet)

    def on_link_packet(self, packet):
        self.device.send_packet(packet)

    def cleanup(self):
        if self.network_configured:
            self.device.restore_network(*self.configuration_parameters())
        # hook = self.config.get("hooks", {}).get("stop", None)
        # if hook:
        #     self.run_os_command(hook)
        self.device.set_packet_callback(None)
        self.link.set_packet_callback(None)
        self.link.cleanup()
        self.device.cleanup()
