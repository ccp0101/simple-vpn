import sys
import os
import argparse
import logging
import json
import tornado.ioloop
from .utils import import_class
from devices.tun import TUNDeviceManager
from session import Session
import tornado.gen
import uuid
from datetime import timedelta
import atexit


class Application(object):
    def __init__(self, mode, config):
        format = "%(levelname)1.1s %(asctime)s %(module)s:%(lineno)d\t%(name)s\t%(message)s"

        parser = argparse.ArgumentParser(
            description='A simple VPN implementation with flexible data transportation.')
        parser.add_argument('--logging', type=str, default='info',
            help='Log level: debug, info, warning, or error. (Default:info)')
        args = parser.parse_args()

        level = args.logging
        if level.lower() not in ['debug', 'info', 'warning', 'error']:
            print >> sys.stderr, "Unknown log level: " + level
        level = getattr(logging, level.upper())

        logging.basicConfig(level=level, format=format)
        self.logger = logging.getLogger("app")
        self.io_loop = tornado.ioloop.IOLoop(impl=tornado.ioloop._Select())
        self.io_loop.install()
        self.mode = mode
        self.config = config
        self.config.setdefault("link", {})
        self.config.setdefault("rewriters", [])
        self.config.setdefault("device", {})
        self.session = None
        self.cleaned_up = None

        if "class" not in self.config["link"]:
            self.logger.error("Must define class in link configuration.")
            sys.exit(1)

        if "class" not in self.config["device"]:
            self.logger.error("Must define class in device configuration.")
            sys.exit(1)

        try:
            link_cls = import_class(self.config["link"]["class"])
            device_cls = import_class(self.config["device"]["class"])
        except ImportError as e:
            self.logger.error(str(e))
            sys.exit(1)

        link_manager_cls = link_cls.get_manager_class(self.mode)
        device_manager_cls = device_cls.get_manager_class(self.mode)
        self.link_manager = link_manager_cls(self.config["link"])
        self.device_manager = device_manager_cls(self.config["device"])

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
                yield tornado.gen.Task(self.io_loop.add_timeout, timedelta(seconds=1))
                link = yield tornado.gen.Task(self.link_manager.create)

            device = yield tornado.gen.Task(self.device_manager.create)

            session = Session(self.mode, self.config, device, link, name=self.session_name)
            self.sessions.append(session)
            session.setup(self.session_closed)
            self.add_new_session()

    def session_closed(self, session):
        session.cleanup()
        self.sessions.remove(session)
        self.add_new_session()

    def run(self):
        self.io_loop.add_callback(self._run)
        try:
            atexit.register(self.cleanup)
            self.io_loop.start()
        except KeyboardInterrupt:
            self.cleanup()

    def cleanup(self):
        if not self.cleaned_up:
            self.cleaned_up = True
            self.logger.info("cleaning up...")
            for session in self.sessions:
                session.cleanup()
            self.link_manager.cleanup()
            self.device_manager.cleanup()
        self.io_loop.stop()
