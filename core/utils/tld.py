import tornado.httpclient
import tornado.gen
import logging
import sys
import os
from datetime import datetime
import string


TLDS_URL = "http://mxr.mozilla.org/mozilla-central/source/netwerk/dns/effective_tld_names.dat?raw=1"

cur_dir = os.path.dirname(os.path.realpath(__file__))
addons_dir = os.path.join(cur_dir, "../addons")
tlds_filepath = os.path.join(addons_dir, "tlds.txt")


if not os.path.isdir(addons_dir):
    logging.error("Addons directory " + addons_dir, " does not exist. ")
    sys.exit(1)


@tornado.gen.engine
def fetch_tlds(callback):
    client = tornado.httpclient.AsyncHTTPClient()
    response = yield tornado.gen.Task(client.fetch, TLDS_URL)
    if response.error:
        logging.error("cannot fetch TLDs. " + str(response.error))
        callback(None)
    else:
        body = response.body
        tlds = []
        for line in body.splitlines():
            domain = line.strip().split("//")[0].split(".")[-1]
            if domain and all([letter in string.ascii_letters
                              for letter in domain]) and domain not in tlds:
                tlds.append(domain)
        callback(tlds)


@tornado.gen.engine
def save_tlds(callback):
    tlds = yield tornado.gen.Task(fetch_tlds)
    if tlds is not None:
        with open(tlds_filepath, "w") as f:
            f.write("# TLDS generated on " + str(datetime.now()) + "\n")
            for tld in tlds:
                f.write(tld + "\n")
    callback()


def load_tlds():
    if not os.path.isfile(tlds_filepath):
        logging.error(tlds_filepath + " does not exist.")
        logging.error('''use "python %s" to generate that file.''')
    with open(tlds_filepath, "r") as f:
        lines = f.readlines()
        tlds = map(lambda x: x.split("#")[0].strip(), lines)
        tlds = filter(len, tlds)
        return tlds


if __name__ == "__main__":
    io_loop = tornado.ioloop.IOLoop.instance()

    @tornado.gen.engine
    def exit_after_finish():
        yield tornado.gen.Task(save_tlds)
        io_loop.stop()

    io_loop.add_callback(exit_after_finish)
    io_loop.start()
