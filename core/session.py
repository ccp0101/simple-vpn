import logging
import subprocess
import uuid
import functools


class Session(object):
    def __init__(self, config, device, link, name=None):
        self.config = config
        self.device = device
        self.name = name or uuid.uuid4().hex
        self.link = link
        self.logger = logging.getLogger("session[%s,%s]" % (str(self.device),
            str(self.link)))
        self.close_callback = None
        self.setup_callback = None
        self.logger.debug("created.")

    def setup(self, close_callback):
        real_callback = functools.partial(close_callback, self)
        self.link.set_close_callback(real_callback)
        self.device.setup()
        self.logger.info("device initiated!")
        hook = self.config.get("hooks", {}).get("start", None)
        if hook:
            self.run_os_command(hook)
        self.device.set_packet_callback(self.on_device_packet)
        self.link.set_packet_callback(self.on_link_packet)
        self.logger.info("session initiated!")

    def run_os_command(self, command, raise_error=False):
        ret = -1
        try:
            ret = subprocess.check_call(command, shell=True)
        except subprocess.CalledProcessError:
            if raise_error:
                raise
        return ret

    def on_device_packet(self, packet):
        self.link.send_packet(packet)

    def on_link_packet(self, packet):
        self.device.send_packet(packet)

    def cleanup(self):
        hook = self.config.get("hooks", {}).get("stop", None)
        if hook:
            self.run_os_command(hook)
        self.device.set_packet_callback(None)
        self.link.set_packet_callback(None)
        self.link.cleanup()
        self.device.cleanup()
