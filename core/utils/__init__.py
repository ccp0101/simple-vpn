import subprocess
import logging
import sys


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
        command = "/sbin/route get " + addr
    else:
        command = "/sbin/ip route get " + addr
    try:
        out = subprocess.check_output(command, shell=True)
    except subprocess.CalledProcessError as e:
        logging.warning("\"%s\" returned %d" % (command, e.returncode))
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
    logging.info("executing: %s" % command)
    try:
        subprocess.check_call(command, shell=True)
    except subprocess.CalledProcessError as e:
        logging.warning("returned %d" % e.returncode)
        return e.returncode
    return 0
