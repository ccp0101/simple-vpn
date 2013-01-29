from core.application import Application

if __name__ == "__main__":
    app = Application("server", {
        "device": {
            "class": "core.devices.tun.TUNDevice"
        },
        "link": {
            "class": "core.links.tcp.TCPLink",
            "port": 20124,
        },
        "rewriters": [
            {
                "class": "core.rewriters.dns.NameserverRewriter",
                "force_nameserver": "8.8.8.8"
            }
        ],
        "network": "10.48.0.0/24"
        })
    app.run()
