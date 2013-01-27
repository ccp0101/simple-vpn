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
