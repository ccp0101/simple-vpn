import logging
import uuid
import functools
import ipaddr
import traceback
import tornado.stack_context
from .utils import import_class


class IPAddressSpaceManager(object):
    def __init__(self, definition):
        self.definition = definition
        self.network = ipaddr.ip_network(self.definition)
        self.hosts = list(self.network.iterhosts())
        self.rewriters = []
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
        self.ip_allocated = False
        self.rewriters = []
        self.message_callbacks = {}
        self.addons = []
        self.original_dns = []
        self.old_nameservers = None
        self.network_configured = False

        for rewriter_config in self.config["rewriters"]:
            if "class" not in rewriter_config:
                self.logger.error("Must define class in rewriter configuration: %s" % rewriter_config)
            else:
                class_name = rewriter_config["class"]
                try:
                    rewriter_cls = import_class(class_name)
                except ImportError as e:
                    self.logger.error(str(e))
                    continue
                rewriter = rewriter_cls(rewriter_config)
                rewriter.setup()
                self.rewriters.append(rewriter)

        for addon_config in self.config["addons"]:
            if "class" not in addon_config:
                self.logger.error("Must define class in addon configuration: %s" % rewriter_config)
            else:
                class_name = addon_config["class"]
                try:
                    addon_cls = import_class(class_name)
                except ImportError as e:
                    self.logger.error(str(e))
                    continue
                addon = addon_cls(addon_config, self)
                addon.setup()
                self.addons.append(addon)

        self.logger.debug("created.")

    def setup(self, close_callback):
        self.link.set_message_callback(self.on_message)
        real_callback = functools.partial(close_callback, self)
        self.link.set_close_callback(real_callback)
        self.device.setup()
        self.logger.info("device initiated!")

        if self.mode == "server":
            self.ip_manager = IPAddressSpaceManager(self.config['network'])
        else:
            self.link.send_message({
                "type": "ip_request"
                })

    def add_message_callback(self, _type, callback):
        self.message_callbacks[_type] = tornado.stack_context(callback)

    def on_message(self, msg):
        if msg.get("type") == "ip_request" and self.mode == "server":
            self.server_ip, self.client_ip = self.ip_manager.allocate(
                ), self.ip_manager.allocate()
            self.ip_allocated = True
            self.link.send_message({
                "type": "ip_reply",
                "server_ip": self.server_ip,
                "network":  self.config['network'],
                "client_ip": self.client_ip,
                })
        elif msg.get("type") == "ip_confirm" and self.mode == "server":
            self.finalize_session()
        elif msg.get("type") == "ip_reply" and self.mode == "client":
            self.server_ip = msg["server_ip"]
            self.client_ip = msg["client_ip"]
            self.link.send_message({"type": "ip_confirm"})
            self.finalize_session()
        else:
            callback = self.message_callbacks.get(msg["type"], None)
            callback(msg)

    def configuration_parameters(self):
        #  peer_pub_ip, peer_ip=None, my_ip=None
        if self.mode == "client":
            return (self.link.ip_endpoint, self.server_ip, self.client_ip)
        else:
            return ("0.0.0.0", self.client_ip, self.server_ip)

    def finalize_session(self):
        self.logger.debug("configuring network.")
        self.device.configure_network(*self.configuration_parameters(),
            set_default_routes=(self.mode == "client" and self.config.get("set_default_gateway", True)))

        for addon in self.addons:
            addon.on_session_established()

        self.network_configured = True

        self.device.set_packet_callback(self.on_device_packet)
        self.link.set_packet_callback(self.on_link_packet)
        self.logger.info("session initiated!")

    def on_device_packet(self, packet):
        data = packet.payload
        for rewriter in self.rewriters:
            try:
                modified = rewriter.rewrite(data)
                if modified != None:
                    data = modified
            except:
                self.logger.error(traceback.format_exc())
                break

        packet.payload = data
        self.link.send_packet(packet)

    def on_link_packet(self, packet):
        data = packet.payload
        for rewriter in self.rewriters:
            try:
                modified = rewriter.rewrite(data)
                if modified != None:
                    data = modified
            except:
                self.logger.error(traceback.format_exc())
                break

        packet.payload = data
        self.device.send_packet(packet)

    def cleanup(self):
        for addon in self.addons:
            addon.cleanup()

        if self.network_configured:
            self.device.restore_network(*self.configuration_parameters())
        if self.ip_allocated:
            self.ip_manager.release(self.server_ip)
            self.ip_manager.release(self.client_ip)

        self.device.set_packet_callback(None)
        self.link.set_packet_callback(None)

        for rewriter in self.rewriters:
            rewriter.cleanup()

        self.link.cleanup()
        self.device.cleanup()
