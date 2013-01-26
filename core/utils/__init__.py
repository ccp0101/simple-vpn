# used for port validation. returns True if valid.
validate_port = lambda p: isinstance(p, int) and p > 0 and p < 65535


# base class for all exceptions raised within this app.
class Error(Exception):
    pass
