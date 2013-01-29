from core.application import Application

if __name__ == "__main__":
    app = Application("client", {
        "device": {
            "class": "core.devices.tun.TUNDevice"
        },
        "link": {
            "class": "core.links.tcp.TCPLink",
            "port": 20124,
            "host": "143.89.220.80"
            # "host": "127.0.0.1",
            # "host": "10.0.2.17",
            # "host": "184.82.229.13",
        },
        })
    app.run()
