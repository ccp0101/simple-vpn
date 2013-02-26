from core.application import Application

if __name__ == "__main__":
    app = Application("client", {
        "device": {
            "class": "core.devices.tun.TUNDevice"
        },
        "link": {
            "class": "core.links.tcp.TCPLink",
            "port": 20121,
#            "host": "119.37.197.34"
#            "host": "143.89.220.80"
            # "host": "127.0.0.1",
            # "host": "10.0.2.17",
            "host": "184.82.229.13",
        },
        "addons": [
            # {
            #     "class": "core.addons.local_nameserver.LocalNameserver",
            #     "remote": "8.8.8.8"
            # },
            {
                "class": "core.addons.nameserver_override.NameserversEditor",
                "nameservers": [
                    "8.8.4.4",
                ]
            }
        ],
        "set_default_gateway":  True
        })
    app.run()
