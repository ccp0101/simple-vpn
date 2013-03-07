import binascii
import subprocess
import logging
import sys
import os
import tornado.ioloop


logger = logging.getLogger("utils")

# used for port validation. returns True if valid.
validate_port = lambda p: isinstance(p, int) and p > 0 and p < 65535


# base class for all exceptions raised within this app.
class Error(Exception):
    pass


# hex dump debugging function
# src: http://code.activestate.com/recipes/142812-hex-dumper/
def hexdump(src, length=8):
    result = []
    digits = 4 if isinstance(src, unicode) else 2
    for i in xrange(0, len(src), length):
        s = src[i:i+length]
        hexa = b' '.join(["%0*X" % (digits, ord(x))  for x in s])
        text = b''.join([x if 0x20 <= ord(x) < 0x7F else b'.'  for x in s])
        result.append( b"%04X   %-*s   %s" % (i, length*(digits + 1), hexa, text) )
    return b'\n'.join(result)


def get_route(addr):
    """
    Executes a system command to retrieve the route for specific address
    @returns (gateway_ip, gateway_ifname)
    For Linux: ip route get <address>
    For Mac: route get <address>
    """
    if "darwin" in sys.platform:
        command = "/sbin/route -n get " + addr
    else:
        command = "/sbin/ip route get " + addr
    try:
        out = subprocess.check_output(command, shell=True)
    except subprocess.CalledProcessError as e:
        logger.warning("\"%s\" returned %d" % (command, e.returncode))
        return ('', '')

    if "darwin" in sys.platform:
        lines = filter(lambda x: ":" in x, out.splitlines())
        mapped = dict(map(lambda x: tuple(x.replace(" ", "").split(":")), lines))
        return (mapped.get('gateway', ''), mapped.get('interface', ''))
    else:
        comps = out.strip().split()
        return (comps[2], comps[4])


def run_os_command(command, params=[], supress_error=True):
    command = command + " " + " ".join(params)
    logger.info("executing: %s" % command)
    try:
        subprocess.check_call(command, shell=True)
    except subprocess.CalledProcessError as e:
        logger.warning("returned %d" % e.returncode)
        return e.returncode
    return 0


def random_bytes(size):
    return bytes(os.urandom(size))


def hexify(data):
    return binascii.b2a_hex(data)


def read_packet(fd, io_loop=None, max_size=2048, callback=None):
    if callback is None:
        raise TypeError()
    else:
        io_loop = io_loop or tornado.ioloop.IOLoop.instance()

        def _callback(fd, events):
            io_loop.remove_handler(fd)
            data, addr = fd.recvfrom(max_size)
            callback((data, addr))

        io_loop.add_handler(fd, _callback, io_loop.READ)


def import_class(cl):
    d = cl.rfind(".")
    classname = cl[d + 1: len(cl)]
    m = __import__(cl[0:d], globals(), locals(), [classname])
    return getattr(m, classname)


class ExceptionIgnoredExecution(object):
    def __init__(self, logger=logger):
        super(ExceptionIgnoredExecution, self).__init__()
        self.logger = logger

    def __enter__(self):
        pass

    def __exit__(self, *args, **kwargs):
        pass
