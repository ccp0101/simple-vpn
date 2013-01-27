import sys
import os
import argparse
import logging
import json
import tornado.ioloop
from links.tcp import TCPLinkClientManager, TCPLinkServerManager
# from devices.bsd import DivertSocketDeviceManager
from devices.tun import TUNDeviceManager
from session import Session
import tornado.gen
import uuid
from datetime import timedelta


class Application(object):
    def __init__(self, mode, config):
        format = "%(levelname)1.1s %(asctime)s %(module)s:%(lineno)d\t%(name)s\t%(message)s"
        logging.basicConfig(level=logging.DEBUG, format=format)
        self.logger = logging.getLogger("app")
        self.io_loop = tornado.ioloop.IOLoop(impl=tornado.ioloop._Select())
        self.io_loop.install()
        self.mode = mode
        self.config = config
        self.session = None
        if self.mode == "client":
            self.link_manager = TCPLinkClientManager(self.config['link'])
            self.device_manager = TUNDeviceManager(self.config['device'])
        else:
            self.link_manager = TCPLinkServerManager(self.config['link'])
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
            link = None
            while link is None:
                link = yield tornado.gen.Task(self.link_manager.create)
                yield tornado.gen.Task(self.io_loop.add_timeout, timedelta(seconds=1))
            link.setup()
            device = yield tornado.gen.Task(self.device_manager.create)

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
