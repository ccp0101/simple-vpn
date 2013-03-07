import logging
import uuid
import functools
import traceback
import tornado.stack_context
from .utils import import_class, ExceptionIgnoredExecution
from .networking.ip import IPAddressSpaceManager


class Session(object):
    def __init__(self, mode, config, device, link, name=None):
        self.mode = mode
        self.config = config
        self.device = device
        self.name = name or uuid.uuid4().hex
        self.link = link
        self.logger = logging.getLogger("session[%s,%s]" % (str(self.device),
            str(self.link)))
        self.message_callbacks = {}
        self.rewriter_callbacks = []
        self.addons = []
        self.network_configured = False

        for addon_config in self.config["addons"]:
            if "class" not in addon_config:
                self.logger.error("Must define class in addon configuration: %s" % addon_config)
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

    def setup_completed(self):
        raise NotImplemented()

    def setup(self, close_callback):
        self.link.set_message_callback(self.on_message)
        real_callback = functools.partial(close_callback, self)
        self.link.set_close_callback(real_callback)
        self.device.setup()
        self.logger.info("device initiated!")
        self.setup_completed()

    def add_message_callback(self, _type, callback):
        self.message_callbacks[_type] = tornado.stack_context.wrap(callback)

    def add_rewriter_callback(self, callback):
        self.rewriter_callbacks.append(tornado.stack_context(callback))

    def on_message(self, msg):
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
            with ExceptionIgnoredExecution(self.logger):
                addon.on_session_established()

        self.network_configured = True

        self.device.set_packet_callback(self.on_device_packet)
        self.link.set_packet_callback(self.on_link_packet)
        self.logger.info("session initiated!")

    def on_device_packet(self, packet):
        data = packet.payload

        for rewriter in self.rewriter_callbacks:
            with ExceptionIgnoredExecution:
                data = rewriter(data)

        packet.payload = data
        self.link.send_packet(packet)

    def on_link_packet(self, packet):
        data = packet.payload
        for rewriter in self.rewriter_callbacks:
            with ExceptionIgnoredExecution:
                modified = rewriter(data)
                if modified != None:
                    data = modified

        packet.payload = data
        self.device.send_packet(packet)

    def cleanup(self):
        for addon in self.addons:
            with ExceptionIgnoredExecution():
                addon.cleanup()

        if self.network_configured:
            with ExceptionIgnoredExecution():
                self.device.restore_network(*self.configuration_parameters())

        self.device.set_packet_callback(None)
        self.link.set_packet_callback(None)

        with ExceptionIgnoredExecution():
            self.link.cleanup()
        with ExceptionIgnoredExecution():
            self.device.cleanup()


class ServerSession(Session):
    def __init__(self, *args, **kwargs):
        super(ServerSession, self).__init__(*args, **kwargs)
        self.ip_allocated = False

    def setup_completed(self):
        self.add_message_callback("ip_request", self.on_ip_request)
        self.add_message_callback("ip_confirm", self.on_ip_confirm)
        self.ip_manager = IPAddressSpaceManager(self.config['network'])

    def on_ip_request(self):
        self.server_ip, self.client_ip = self.ip_manager.allocate(
            ), self.ip_manager.allocate()
        self.ip_allocated = True
        self.link.send_message({
            "type": "ip_reply",
            "server_ip": self.server_ip,
            "network":  self.config['network'],
            "client_ip": self.client_ip,
            })

    def on_ip_confirm(self):
        self.finalize_session()

    def cleanup(self):
        if self.ip_allocated:
            self.ip_manager.release(self.server_ip)
            self.ip_manager.release(self.client_ip)

        super(ServerSession, self).cleanup()


class ClientSession(Session):
    def setup_completed(self):
        print "A"
        self.add_message_callback("ip_reply", self.on_ip_reply)
        self.link.send_message({
                "type": "ip_request"
                })

    def on_ip_reply(self, msg):
        print "B"
        self.server_ip = msg["server_ip"]
        self.client_ip = msg["client_ip"]
        self.link.send_message({"type": "ip_confirm"})
        self.finalize_session()
