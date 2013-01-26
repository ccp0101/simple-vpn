import sys
import os
import argparse
import logging
import json
import tornado.ioloop
from links.tcp import TCPLinkClientManager
# from devices.bsd import DivertSocketDeviceManager
from devices.tun import TUNDeviceManager
from session import Session
import tornado.gen
import uuid


class Application(object):
    def __init__(self, mode, config):
        logging.basicConfig(level=logging.DEBUG)
        self.logger = logging.getLogger("app")
        self.io_loop = tornado.ioloop.IOLoop(impl=tornado.ioloop._Select())
        self.io_loop.install()
        self.mode = mode
        self.config = config
        self.session = None
        self.link_manager = TCPLinkClientManager(self.config['link'])
        self.device_manager = TUNDeviceManager(self.config['device'])
        self.sessions = []

    def _run(self):
        self.link_manager.setup()
        self.device_manager.setup()

        if self.mode == "client":
            self.session_name = uuid.uuid4().hex
        else:
            self.session_name = None

        self.max_session_size = 1 if self.mode == "client" else 10
        self.add_new_session()

    @tornado.gen.engine
    def add_new_session(self):
        if len(self.sessions) < self.max_session_size:
            link = yield tornado.gen.Task(self.link_manager.create)
            link.setup()
            device = yield tornado.gen.Task(self.device_manager.create)
            device.setup()

            session = Session(self.config, device, link, name=self.session_name)
            session.setup(self.session_closed)
            self.sessions.append(session)
            self.add_new_session()

    def session_closed(self, session):
        session.cleanup()
        self.sessions.remove(session)
        self.add_new_session()

    def run(self):
        self.io_loop.add_callback(self._run)
        try:
            self.io_loop.start()
        except KeyboardInterrupt:
            self.cleanup()

    def cleanup(self):
        self.logger.info("cleaning up...")
        for session in self.sessions:
            session.cleanup()
        self.link_manager.cleanup()
        self.device_manager.cleanup()
        self.io_loop.stop()
