from core.application import Application

if __name__ == "__main__":
    app = Application("client", {
        "device": {
            "class": "core.devices.tun.TUNDevice"
        },
        "link": {
            "class": "core.links.tcp.TCPLink",
            "port": 20121,
            "host": "184.82.229.13",
        },
        "addons": [
            {
                "class": "core.addons.nameserver_override.NameserversEditor",
                "nameservers": [
                    "8.8.4.4",
                    "208.67.222.222",
                ]
            }
        ],
        "set_default_gateway":  True
        })
    app.run()
