import logging
import uuid
import functools
import ipaddr
import traceback
from .utils import import_class
import subprocess
import re
import sys


class NameserversEditor(object):
    def __init__(self, nameservers):
        self.nameservers = nameservers
        self.original_nameservers = None
        self.logger = logging.getLogger("nameservers-editor")

    def get_scutil_output(self, stdin, command="/usr/sbin/scutil"):
        self.logger.debug("invoking " + command + " with: " + stdin)
        try:
            p = subprocess.Popen(command, shell=True,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE)
            stdout, stderr = p.communicate(stdin)
            if p.returncode != 0:
                raise subprocess.CalledProcessError(returncode=p.returncode)
        except:
            self.logger.warning(traceback.format_exc())
            return ""
        return stdout

    def set(self):
        if "darwin" in sys.platform:
            stdin = """
                open
                get State:/Network/Global/IPv4
                d.show
                quit
            """
            out = self.get_scutil_output(stdin,
                "/usr/sbin/scutil | grep 'PrimaryService' | awk '{print $3}'").strip()
            if not re.match(r'[A-Z0-9a-z]{8}-[A-Z0-9a-z]{4}-[A-Z0-9a-z]{4}-[A-Z0-9a-z]{4}-[A-Z0-9a-z]{12}',
                    out):
                self.logger.warning("did not get primary service ID from scutil: " + out)
                return
            else:
                self.service_id = out

            stdin = """
                open
                get State:/Network/Service/%s/DNS
                d.show
                quit
            """ % self.service_id

            out = self.get_scutil_output(stdin)
            out = out.replace("\n", " ")
            server_addresses = re.findall(r'ServerAddresses[^{]+\{(.+)\}', out)
            if len(server_addresses) != 1:
                self.logger.warning("cannot parser: " + out)
                return

            _nameservers = re.findall(r'(\d{0,3}\.\d{0,3}\.\d{0,3}\.\d{0,3})', server_addresses[0])
            _domain_name = re.findall(r'DomainName\s+\:\s+([^\s\}]+)[\s\}]', out)
            _domain_name = _domain_name[0] if len(_domain_name) else None
            self.logger.debug("found existing nameservers: %s and domain name: %s" %
                (str(_nameservers), str(_domain_name)))

            domain_name_config = ""
            if _domain_name:
                domain_name_config = "d.add DomainName " + _domain_name

            stdin = """open
                    d.init
                    d.add ServerAddresses * %s
                    %s
                    set State:/Network/Service/%s/DNS
                    quit
                    """ % (" ".join(self.nameservers), domain_name_config, self.service_id)

            out = self.get_scutil_output(stdin).strip()
            if len(out) != 0:
                self.logger.warning("cannot set name configurations with scutil.")
                return

            self.original_nameservers = _nameservers
            self.original_domain = _domain_name
            self.logger.info("original nameservers: %s, new nameservers: %s" %
                (str(_nameservers), str(self.nameservers)))
        else:
            self.logger.warning("I don't know how to set nameservers in non-Mac")

    def restore(self):
        if self.original_nameservers:
            domain_string = ""
            if self.original_domain:
                domain_string = "d.add DomainName %s" % self.original_domain
            stdin = """open
                    d.init
                    d.add ServerAddresses * %s
                    %s
                    set State:/Network/Service/%s/DNS
                    quit
                    """ % (" ".join(self.original_nameservers),
                        domain_string, self.service_id)

            out = self.get_scutil_output(stdin).strip()
            if len(out) != 0:
                self.logger.warning("cannot set name configurations with scutil.")


class IPAddressSpaceManager(object):
    def __init__(self, definition):
        self.definition = definition
        self.network = ipaddr.ip_network(self.definition)
        self.hosts = list(self.network.iterhosts())
        self.rewriters = []

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
        self.original_dns = []
        self.old_nameservers = None
        self.network_configured = False
        self.nameservers_editor = None

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

    def configuration_parameters(self):
        #  peer_pub_ip, peer_ip=None, my_ip=None
        if self.mode == "client":
            return (self.link.ip_endpoint, self.server_ip, self.client_ip)
        else:
            return ("0.0.0.0", self.client_ip, self.server_ip)

    def finalize_session(self):
        self.logger.debug("configuring network.")
        self.device.configure_network(*self.configuration_parameters(),
            set_default_routes=(self.mode == "client"))
        if "nameservers" in self.config:
            self.nameservers_editor = NameserversEditor(self.config["nameservers"])
            self.nameservers_editor.set()

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
        if self.nameservers_editor:
            self.nameservers_editor.restore()

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
