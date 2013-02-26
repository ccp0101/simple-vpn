import sys
import logging
import subprocess
import traceback
import re
from .abstract import Addon
import errno
import os
import time
import tempfile
from ..utils.tld import load_tlds
import shutil


# class NetworkServiceNameserversEditor(Addon):
#     def __init__(self, config, session):
#         super(NetworkServiceNameserversEditor, self).__init__(config, session)
#         self.nameservers = config['nameservers']
#         self.original_nameservers = None
#         self.logger = logging.getLogger("nameservers-editor")

#     def on_session_established(self):
#         self.set()

#     def get_scutil_output(self, stdin, command="/usr/sbin/scutil"):
#         self.logger.debug("invoking " + command + " with: " + stdin)
#         try:
#             p = subprocess.Popen(command, shell=True,
#                 stdin=subprocess.PIPE, stdout=subprocess.PIPE)
#             stdout, stderr = p.communicate(stdin)
#             if p.returncode != 0:
#                 raise subprocess.CalledProcessError(returncode=p.returncode)
#         except:
#             self.logger.warning(traceback.format_exc())
#             return ""
#         return stdout

#     def set(self):
#         if "darwin" in sys.platform:
#             stdin = """
#                 open
#                 get State:/Network/Global/IPv4
#                 d.show
#                 quit
#             """
#             out = self.get_scutil_output(stdin,
#                 "/usr/sbin/scutil | grep 'PrimaryService' | awk '{print $3}'").strip()
#             if not re.match(r'[A-Z0-9a-z]{8}-[A-Z0-9a-z]{4}-[A-Z0-9a-z]{4}-[A-Z0-9a-z]{4}-[A-Z0-9a-z]{12}',
#                     out):
#                 self.logger.warning("did not get primary service ID from scutil: " + out)
#                 return
#             else:
#                 self.service_id = out

#             stdin = """
#                 open
#                 get State:/Network/Service/%s/DNS
#                 d.show
#                 quit
#             """ % self.service_id

#             out = self.get_scutil_output(stdin)
#             out = out.replace("\n", " ")
#             server_addresses = re.findall(r'ServerAddresses[^{]+\{(.+)\}', out)
#             if len(server_addresses) != 1:
#                 self.logger.warning("cannot parser: " + out)
#                 return

#             _nameservers = re.findall(r'(\d{0,3}\.\d{0,3}\.\d{0,3}\.\d{0,3})', server_addresses[0])
#             _domain_name = re.findall(r'DomainName\s+\:\s+([^\s\}]+)[\s\}]', out)
#             _domain_name = _domain_name[0] if len(_domain_name) else None
#             self.logger.debug("found existing nameservers: %s and domain name: %s" %
#                 (str(_nameservers), str(_domain_name)))

#             domain_name_config = ""
#             if _domain_name:
#                 domain_name_config = "d.add DomainName " + _domain_name

#             stdin = """open
#                     d.init
#                     d.add ServerAddresses * %s
#                     %s
#                     set State:/Network/Service/%s/DNS
#                     quit
#                     """ % (" ".join(self.nameservers), domain_name_config, self.service_id)

#             out = self.get_scutil_output(stdin).strip()
#             if len(out) != 0:
#                 self.logger.warning("cannot set name configurations with scutil.")
#                 return

#             self.original_nameservers = _nameservers
#             self.original_domain = _domain_name
#             self.logger.info("original nameservers: %s, new nameservers: %s" %
#                 (str(_nameservers), str(self.nameservers)))
#         else:
#             self.logger.warning("I don't know how to set nameservers in non-Mac")

#     def restore(self):
#         if self.original_nameservers:
#             domain_string = ""
#             if self.original_domain:
#                 domain_string = "d.add DomainName %s" % self.original_domain
#             stdin = """open
#                     d.init
#                     d.add ServerAddresses * %s
#                     %s
#                     set State:/Network/Service/%s/DNS
#                     quit
#                     """ % (" ".join(self.original_nameservers),
#                         domain_string, self.service_id)

#             out = self.get_scutil_output(stdin).strip()
#             if len(out) != 0:
#                 self.logger.warning("cannot set name configurations with scutil.")

#     def cleanup(self):
#         self.restore()


class NameserversEditor(Addon):
    def __init__(self, config, session):
        super(NameserversEditor, self).__init__(config, session)
        self.nameservers = config['nameservers']
        self.logger = logging.getLogger("nameservers-editor")
        self.tlds = load_tlds()
        self.original_dir = None
        self.tmp_dir = tempfile.mkdtemp()
        self.linked = False

    def on_session_established(self):
        self.set()

    def set(self):
        content = ""
        for nameserver in self.nameservers:
            content += "nameserver %s\n" % nameserver

        self.tmp_dir = tempfile.mkdtemp()

        for tld in self.tlds:
            with open(os.path.join(self.tmp_dir, tld), "w") as f:
                f.write(content)

        if os.path.isdir("/etc/resolver"):
            original = "/etc/resolver_%d" % int(time.time())
            os.renames("/etc/resolver", original)
            self.original_dir = original

        os.symlink(self.tmp_dir, "/etc/resolver")
        self.linked = True

    def restore(self):
        if self.linked:
            os.unlink("/etc/resolver")

        shutil.rmtree(self.tmp_dir)

        if self.original_dir:
            os.renames(self.original_dir, "/etc/resolver")

    def cleanup(self):
        self.restore()
